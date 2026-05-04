import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import Website
from scraper.models import Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper
from scraper.status import detect_status

# Funda card subtitle is "<postcode> <city>" inside div.truncate.text-neutral-80,
# e.g. "2024 CB Haarlem".
_FUNDA_POSTCODE_PREFIX = re.compile(r"^\s*\d{4}\s?[A-Z]{2}\s+", re.IGNORECASE)
# Used to identify the smallest ancestor that wraps a single card.
_POSTCODE_RE = re.compile(r"\b\d{4}\s?[A-Z]{2}\b")


class FundaScraper(BaseScraper):
    website = Website.FUNDA
    detection_markers = ("Je bent bijna op de pagina die je zoekt",)
    MAX_PAGES = 5

    def __init__(self, fetch: FetchStrategy, base_url: str = "https://www.funda.nl/zoeken/koop") -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Funda (since={since})")
        last_page = self._get_last_page()
        listings: list[Listing] = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {len(listings)} listings across {last_page} pages")
        return listings

    def _scrape_page(self, page_number: int) -> list[Listing]:
        page_url = self._append_page_number(self.base_url, page_number)
        soup = self.get_soup(page_url)
        return [self._parse_card(card) for card in self._iter_cards(soup)]

    @staticmethod
    def _iter_cards(soup: BeautifulSoup) -> Iterator[Tag]:
        # Funda's list HTML has no stable per-card class. Anchor on each unique
        # listingDetailsAddress link and walk up to the smallest ancestor that
        # holds the postcode subtitle, a "€" price, an <img>, and only that one
        # detail URL — that ancestor is the card root.
        seen: set[str] = set()
        for anchor in soup.select('a[data-testid="listingDetailsAddress"]'):
            href = str(anchor.get("href", ""))
            if not href or href in seen:
                continue
            card = _find_card_root(anchor, href)
            if card is None:
                logger.warning(f"Could not locate card root for {href}")
                continue
            seen.add(href)
            yield card

    def _parse_card(self, card: Tag) -> Listing:
        anchor = card.select_one('a[data-testid="listingDetailsAddress"]')
        href = str(anchor.get("href", "")) if anchor else ""
        detail_url = f"https://www.funda.nl{href}"

        title_el = card.select_one('a[data-testid="listingDetailsAddress"] span.truncate')
        title = title_el.get_text(strip=True) if title_el else ""

        subtitle_el = card.select_one("div.truncate.text-neutral-80")
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""
        postcode = parse_dutch_postcode(subtitle)
        city = _FUNDA_POSTCODE_PREFIX.sub("", subtitle).strip() or ""

        street, house_number, house_letter, house_number_suffix = parse_dutch_address(title)

        return Listing(
            detail_url=detail_url,
            title=title,
            price=_extract_price(card),
            city=city,
            street=street,
            house_number=house_number,
            house_letter=house_letter,
            house_number_suffix=house_number_suffix,
            postcode=postcode,
            image_url=_extract_image(card),
            website=self.website,
            status=detect_status(card),
        )

    def _get_last_page(self) -> int:
        soup = self.get_soup(self.base_url)
        page_numbers: list[int] = []
        for link in soup.select("a[href*='page=']"):
            href = str(link.get("href", ""))
            page_str = parse_qs(urlparse(href).query).get("page", [""])[0]
            if page_str.isdigit():
                page_numbers.append(int(page_str))
        if not page_numbers:
            # Funda's pagination is hydrated by Nuxt; if it didn't render in time,
            # speculatively scan up to MAX_PAGES rather than collapsing to 1 page.
            return self.MAX_PAGES
        return min(max(page_numbers), self.MAX_PAGES)

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["search_result"] = [str(page_number)]
        new_query = urlencode(params, doseq=True, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))


def _find_card_root(anchor: Tag, href: str) -> Tag | None:
    parent = anchor.parent
    while parent is not None:
        text = parent.get_text(" ", strip=True)
        if _POSTCODE_RE.search(text) and "€" in text and parent.find("img") is not None:
            inner = {str(a.get("href", "")) for a in parent.select('a[href*="/detail/"]')}
            if inner == {href}:
                return parent
        parent = parent.parent
    return None


def _extract_price(card: Tag) -> str:
    el = card.select_one("div.font-semibold > div.truncate")
    if el and el.get_text(strip=True).startswith("€"):
        return el.get_text(strip=True)
    # Fallback excludes "m²" so a wrapper that bundles price + area metadata
    # (e.g. "€ 720.000 k.k.157 m²306 m²2A") is rejected.
    for div in card.find_all("div"):
        text = div.get_text(strip=True)
        if text.startswith("€") and "m²" not in text and len(text) < 60:
            return text
    return ""


def _extract_image(card: Tag) -> str | None:
    el = card.select_one('img[src*="cloud.funda.nl"]')
    if el is not None:
        src = str(el.get("src", ""))
        if src.startswith(("http://", "https://")):
            return src
    fallback = card.select_one('img[data-src*="cloud.funda.nl"]')
    if fallback is not None:
        data_src = str(fallback.get("data-src", ""))
        if data_src.startswith(("http://", "https://")):
            return data_src
    return None
