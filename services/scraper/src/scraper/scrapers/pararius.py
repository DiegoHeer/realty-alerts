import json
import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import ListingStatus, Website
from scraper.models import DetailListing, Listing
from scraper.parsing import parse_building_type, parse_construction_type
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper
from scraper.status import detect_status

# Pararius card subtitle format: "<postcode> <city> (<neighborhood>)"
# e.g. "3067 ZV Rotterdam (Oosterflank)" — neighborhood is optional.
_PARARIUS_POSTCODE_PREFIX = re.compile(r"^\s*\d{4}\s?[A-Z]{2}\s+", re.IGNORECASE)
_PARARIUS_NEIGHBORHOOD_SUFFIX = re.compile(r"\s*\(.*\)\s*$")


class ParariusScraper(BaseScraper):
    website = Website.PARARIUS
    MAX_PAGES = 5

    def __init__(self, fetch: FetchStrategy, base_url: str = "https://www.pararius.nl/koopwoningen/nederland") -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape_list(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Pararius (since={since})")
        last_page = self._get_last_page()
        listings: list[Listing] = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {len(listings)} listings across {last_page} pages")
        return listings

    def scrape_detail(self, url: str) -> DetailListing:
        soup = self.get_soup(url)
        return self._parse_detail_page(soup)

    def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
        price_el = soup.select_one("div.listing-detail-summary__price")
        price = price_el.get_text(strip=True) if price_el else ""

        status_text = _parse_dd_text(soup, "Status") or ""
        status = _parse_status(status_text.lower())

        surface_el = soup.select_one("dd.listing-features__description--surface_area")
        surface_area_m2 = _parse_first_int(surface_el.get_text(strip=True)) if surface_el else None

        rooms_el = soup.select_one("dd.listing-features__description--number_of_rooms")
        room_count = _parse_first_int(rooms_el.get_text(strip=True)) if rooms_el else None

        beds_el = soup.select_one("dd.listing-features__description--number_of_bedrooms")
        bedroom_count = _parse_first_int(beds_el.get_text(strip=True)) if beds_el else None

        baths_el = soup.select_one("dd.listing-features__description--number_of_bathrooms")
        bathroom_count = _parse_first_int(baths_el.get_text(strip=True)) if baths_el else None

        period_el = soup.select_one("dd.listing-features__description--construction_period")
        construction_period = period_el.get_text(strip=True) or None if period_el else None

        label_el = soup.select_one('dd[class*="listing-features__description--energy-label-"]')
        energy_label = label_el.get_text(strip=True) or None if label_el else None

        postcode = _parse_json_ld_postcode(soup)

        property_types_el = soup.select_one("dd.listing-features__description--property_types")
        building_type_raw = property_types_el.get_text(strip=True) if property_types_el else None
        building_type = parse_building_type(building_type_raw) if building_type_raw else None

        construction_type_el = soup.select_one("dd.listing-features__description--construction_type")
        construction_type_raw = construction_type_el.get_text(strip=True) if construction_type_el else None
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
        anchors = soup.select('ul[class="pagination__list"] li a')
        page_numbers = [int(a.text) for a in anchors if a.text.isdigit()]
        max_page = max(page_numbers) if page_numbers else 1
        return min(max_page, self.MAX_PAGES)

    def _scrape_page(self, page_number: int) -> list[Listing]:
        page_url = self._append_page_number(self.base_url, page_number)
        soup = self.get_soup(page_url)
        cards = soup.select("section.listing-search-item--for-sale")
        return [self._parse_card(card) for card in cards]

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        new_path = PurePosixPath(parsed.path) / f"page-{page_number}"
        return urlunparse(parsed._replace(path=str(new_path)))

    def _parse_card(self, card: Tag) -> Listing:
        url_el = card.select_one("a.listing-search-item__link")
        detail_url = f"https://www.pararius.nl{url_el.get('href')}" if url_el else ""

        title_el = card.select_one("a.listing-search-item__link--title")
        title = title_el.get_text(strip=True) if title_el else ""

        price_el = card.select_one("div.listing-search-item__price")
        price = price_el.get_text().strip() if price_el else ""

        image_el = card.select_one("img.picture__image")
        image_src = str(image_el.get("src", "")) if image_el else ""
        # Pararius lazy-loads thumbnails behind inline SVG data: placeholders;
        # only accept real http(s) URLs to keep payloads under the API's varchar(500) cap.
        image_url = image_src if image_src.startswith(("http://", "https://")) else None

        subtitle_el = card.select_one("div.listing-search-item__sub-title")
        subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ""
        postcode, city = self._parse_subtitle(subtitle)

        street, house_number, house_letter, house_number_suffix = parse_dutch_address(title)

        return Listing(
            detail_url=detail_url,
            title=title,
            price=price,
            city=city or "",
            street=street,
            house_number=house_number,
            house_letter=house_letter,
            house_number_suffix=house_number_suffix,
            postcode=postcode,
            image_url=image_url or None,
            website=self.website,
            status=detect_status(card),
        )

    @staticmethod
    def _parse_subtitle(text: str) -> tuple[str | None, str]:
        postcode = parse_dutch_postcode(text)
        without_postcode = _PARARIUS_POSTCODE_PREFIX.sub("", text)
        city = _PARARIUS_NEIGHBORHOOD_SUFFIX.sub("", without_postcode).strip()
        return postcode, city


def _parse_dd_text(soup: BeautifulSoup, label: str) -> str | None:
    """Return the dd value of a dt/dd kenmerken pair as a string, or None if absent."""
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


def _parse_status(text: str) -> ListingStatus:
    if "voorbehoud" in text or "onder bod" in text:
        return ListingStatus.SALE_PENDING
    if "verkocht" in text:
        return ListingStatus.SOLD
    return ListingStatus.NEW


def _parse_json_ld_postcode(soup: BeautifulSoup) -> str | None:
    """Extract postcode from schema.org JSON-LD address block."""
    script = soup.select_one('script[type="application/ld+json"]')
    if not script or not script.string:
        return None
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return None
    address = data.get("address") if isinstance(data, dict) else None
    if not isinstance(address, dict):
        return None
    return parse_dutch_postcode(address.get("postalCode"))
