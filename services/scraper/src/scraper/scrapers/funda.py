import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import Website
from scraper.models import Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper

# Funda card subtitle is "<postcode> <city>" inside div.truncate.text-neutral-80,
# e.g. "2024 CB Haarlem".
_FUNDA_POSTCODE_PREFIX = re.compile(r"^\s*\d{4}\s?[A-Z]{2}\s+", re.IGNORECASE)
# Used to identify the smallest ancestor that wraps a single card.
_POSTCODE_RE = re.compile(r"\b\d{4}\s?[A-Z]{2}\b")


@dataclass(frozen=True, slots=True)
class _CardAddress:
    street: str | None
    house_number: int | None
    house_number_suffix: str | None
    postcode: str | None
    city: str


class FundaScraper(BaseScraper):
    website = Website.FUNDA
    detection_markers = ("Je bent bijna op de pagina die je zoekt",)
    MAX_PAGES = 5

    def __init__(self, fetch: FetchStrategy, base_url: str = "https://www.funda.nl/zoeken/koop") -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Funda (since={since})")
        cards = self._scrape_listing_pages()
        listings = [self._scrape_detail_page(url, addr) for url, addr in cards.items()]
        return [listing for listing in listings if listing is not None]

    def _scrape_listing_pages(self) -> dict[str, _CardAddress]:
        last_page = self._get_last_page()
        cards: dict[str, _CardAddress] = {}
        for page_number in range(1, last_page + 1):
            page_url = self._append_page_number(self.base_url, page_number)
            soup = self.get_soup(page_url)
            for href, card_addr in self._iter_cards(soup):
                detail_url = f"https://www.funda.nl{href}"
                cards.setdefault(detail_url, card_addr)
        logger.info(f"Found {len(cards)} cards across {last_page} pages")
        return cards

    @staticmethod
    def _iter_cards(soup: BeautifulSoup) -> list[tuple[str, _CardAddress]]:
        # Each Funda card has multiple links pointing at the same detail URL
        # (image, title, etc). Walk up from each unique href until we find the
        # smallest ancestor that holds the postcode subtitle and only that one
        # detail URL — that ancestor is the card root.
        seen: set[str] = set()
        results: list[tuple[str, _CardAddress]] = []
        for anchor in soup.select('a[href^="/detail/"]'):
            href = str(anchor.get("href", ""))
            if not href or href in seen:
                continue
            card = FundaScraper._find_card_root(anchor, href)
            if card is None:
                continue
            seen.add(href)
            results.append((href, FundaScraper._parse_card_address(card)))
        return results

    @staticmethod
    def _find_card_root(anchor: Tag, href: str) -> Tag | None:
        parent = anchor.parent
        while parent is not None:
            if _POSTCODE_RE.search(parent.get_text(" ", strip=True)):
                inner = {str(a.get("href", "")) for a in parent.select('a[href^="/detail/"]')}
                if inner == {href}:
                    return parent
            parent = parent.parent
        return None

    @staticmethod
    def _parse_card_address(card: Tag) -> _CardAddress:
        street_el = card.select_one("span.truncate")
        street_text = street_el.get_text(strip=True) if street_el else ""
        street, house_number, suffix = parse_dutch_address(street_text)

        subtitle_el = card.select_one("div.truncate.text-neutral-80")
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""
        postcode = parse_dutch_postcode(subtitle)
        city = _FUNDA_POSTCODE_PREFIX.sub("", subtitle).strip() or "unknown"

        return _CardAddress(
            street=street,
            house_number=house_number,
            house_number_suffix=suffix,
            postcode=postcode,
            city=city,
        )

    def _get_last_page(self) -> int:
        soup = self.get_soup(self.base_url)
        page_numbers: list[int] = []
        for link in soup.select("a[href*='page=']"):
            href = str(link.get("href", ""))
            page_str = parse_qs(urlparse(href).query).get("page", [""])[0]
            if page_str.isdigit():
                page_numbers.append(int(page_str))
        return min(max(page_numbers, default=1), self.MAX_PAGES)

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["search_result"] = [str(page_number)]
        new_query = urlencode(params, doseq=True, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))

    def _scrape_detail_page(self, detail_url: str, address: _CardAddress) -> Listing | None:
        try:
            soup = self.get_soup(detail_url)
        except Exception:
            logger.warning(f"Failed to scrape detail page: {detail_url}")
            return None

        title = self._get_text(soup, "h1 span.block.text-2xl.font-bold")
        price = self._get_text(soup, "div.flex.gap-2.font-bold > span")
        image_url = self._get_attr(soup, "img.size-full.object-cover", "src")

        return Listing(
            detail_url=detail_url,
            title=title,
            price=price,
            city=address.city,
            street=address.street,
            house_number=address.house_number,
            house_number_suffix=address.house_number_suffix,
            postcode=address.postcode,
            image_url=image_url or None,
            website=self.website,
        )

    @staticmethod
    def _get_text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text().strip() if el else ""

    @staticmethod
    def _get_attr(soup: BeautifulSoup, selector: str, attr: str) -> str:
        el = soup.select_one(selector)
        return str(el.get(attr, "")) if el else ""
