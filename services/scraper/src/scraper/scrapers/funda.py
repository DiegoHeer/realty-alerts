import re
from collections.abc import Iterator
from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import ListingStatus, Website
from scraper.parsing import parse_building_type, parse_construction_type
from scraper.models import DetailListing, Listing
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

    def scrape_list(self, since: datetime | None) -> list[Listing]:
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

    def scrape_detail(self, url: str) -> DetailListing:
        soup = self.get_soup(url)
        return self._parse_detail_page(soup)

    def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
        price_el = soup.select_one("div.flex.flex-col.font-bold.text-xl")
        price = price_el.get_text(strip=True) if price_el else ""

        status_text = _parse_dt_dd_text(soup, "Status") or ""
        status = _parse_status(status_text.lower())

        wonen = _parse_dt_dd_text(soup, "Wonen")
        surface_area_m2 = _parse_first_int(wonen) if wonen else None

        kamers = _parse_dt_dd_text(soup, "Aantal kamers")
        room_count = _parse_kamers_total(kamers) if kamers else None
        bedroom_count = _parse_slaapkamers(kamers) if kamers else None

        badkamers = _parse_dt_dd_text(soup, "Aantal badkamers")
        bathroom_count = _parse_first_int(badkamers) if badkamers else None

        construction_period = _parse_dt_dd_text(soup, "Bouwjaar")

        energy_label = _parse_dt_dd_text(soup, "Energielabel")

        title_el = soup.select_one("title")
        postcode = parse_dutch_postcode(title_el.get_text() if title_el else None)

        building_type_raw = _parse_dt_dd_text(soup, "Soort woonhuis") or _parse_dt_dd_text(soup, "Soort appartement")
        building_type = parse_building_type(building_type_raw) if building_type_raw else None

        construction_type_raw = _parse_dt_dd_text(soup, "Soort bouw")
        construction_type = parse_construction_type(construction_type_raw) if construction_type_raw else None

        return DetailListing(
            price=price,
            status=status,
            surface_area_m2=surface_area_m2,
            bedroom_count=bedroom_count,
            bathroom_count=bathroom_count,
            room_count=room_count,
            construction_period=construction_period,
            energy_label=energy_label,
            postcode=postcode,
            building_type=building_type,
            construction_type=construction_type,
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


def _parse_dt_dd_text(soup: BeautifulSoup, label: str) -> str | None:
    """Return the dd value of a dt/dd pair as a string, or None if absent."""
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True) == label:
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.get_text(strip=True) or None
    return None


def _parse_first_int(text: str) -> int | None:
    """Return the first integer found in text, or None."""
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None


def _parse_kamers_total(text: str) -> int | None:
    """Return total room count from '4 kamers (2 slaapkamers)' style text."""
    m = re.search(r"(\d+)\s+kamers?", text)
    return int(m.group(1)) if m else None


def _parse_slaapkamers(text: str) -> int | None:
    """Return bedroom count from '4 kamers (2 slaapkamers)' style text."""
    m = re.search(r"(\d+)\s+slaapkamers?", text)
    return int(m.group(1)) if m else None


def _parse_status(text: str) -> ListingStatus:
    if "voorbehoud" in text or "onder bod" in text:
        return ListingStatus.SALE_PENDING
    if "verkocht" in text:
        return ListingStatus.SOLD
    return ListingStatus.NEW
