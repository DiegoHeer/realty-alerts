import re
from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup, Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import ListingStatus, Website
from scraper.models import DetailListing, Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper
from scraper.status import detect_status


class VastgoedNLScraper(BaseScraper):
    website = Website.VASTGOED_NL
    MAX_PAGES = 5

    def __init__(
        self, fetch: FetchStrategy, base_url: str = "https://aanbod.vastgoednederland.nl/koopwoningen"
    ) -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape_list(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Vastgoed NL (since={since})")
        last_page = self._get_last_page()
        listings = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {len(listings)} listings across {last_page} pages")
        return listings

    def scrape_detail(self, url: str) -> DetailListing:
        soup = self.get_soup(url)
        return self._parse_detail_page(soup)

    def _get_last_page(self) -> int:
        soup = self.get_soup(self.base_url)
        anchors = soup.select('ul[class="pagination"] li a')
        page_numbers = [int(a.text) for a in anchors if a.text.isdigit()]
        max_page = max(page_numbers) if page_numbers else 1
        return min(max_page, self.MAX_PAGES)

    def _scrape_page(self, page_number: int) -> list[Listing]:
        page_url = self._append_page_number(self.base_url, page_number)
        soup = self.get_soup(page_url)
        cards = soup.select("a.propertyLink")
        return [self._parse_card(card) for card in cards]

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["p"] = [str(page_number)]
        new_query = urlencode(params, doseq=True, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))

    def _parse_card(self, card: Tag) -> Listing:
        detail_url = str(card.get("href", ""))

        title_el = card.select_one("span.street")
        title = title_el.get_text().strip() if title_el else ""

        price_el = card.select_one("span.price")
        price = price_el.get_text().strip() if price_el else ""

        image_el = card.select_one("img")
        image_url = str(image_el.get("src", "")) if image_el else None

        city_el = card.select_one("span.city")
        city = city_el.get_text(strip=True) if city_el else ""

        street, house_number, house_letter, house_number_suffix = parse_dutch_address(title)

        return Listing(
            detail_url=detail_url,
            title=title,
            price=price,
            city=city or "unknown",
            street=street,
            house_number=house_number,
            house_letter=house_letter,
            house_number_suffix=house_number_suffix,
            postcode=None,
            image_url=image_url or None,
            website=self.website,
            status=detect_status(card),
        )

    def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
        price_el = soup.select_one("span.price")
        price = price_el.get_text(strip=True) if price_el else ""

        status_el = soup.select_one("span.info-badge.primary")
        status = _parse_status(status_el.get_text(strip=True).lower() if status_el else "")

        energy_el = soup.select_one("span.energielabel")
        energy_label = energy_el.get_text(strip=True) if energy_el else None

        surface_area_m2 = _parse_summary_int(soup, "Woonoppervlakte")
        room_count = _parse_summary_int(soup, "Aantal kamers")
        bedroom_count = _parse_dt_dd_int(soup, "Aantal slaapkamers")
        bathroom_count = _parse_dt_dd_int(soup, "Aantal badkamers")
        construction_period = _parse_dt_dd_text(soup, "Bouwperiode")

        address_el = soup.select_one("address")
        address_p = address_el.select_one("p") if address_el else None
        postcode = parse_dutch_postcode(address_p.get_text() if address_p else None)

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
        )


def _parse_status(text: str) -> ListingStatus:
    if "voorbehoud" in text:
        return ListingStatus.SALE_PENDING
    if "verkocht" in text:
        return ListingStatus.SOLD
    return ListingStatus.NEW


def _parse_summary_int(soup: BeautifulSoup, label: str) -> int | None:
    """Return the first integer from span.value in the div.col-6 summary card matching label."""
    for div in soup.select("div.col-6"):
        strong = div.select_one("strong")
        if strong and strong.get_text(strip=True) == label:
            value_el = div.select_one("span.value")
            if value_el:
                m = re.search(r"\d+", value_el.get_text(strip=True))
                return int(m.group()) if m else None
    return None


def _parse_dt_dd_int(soup: BeautifulSoup, label: str) -> int | None:
    """Return the dd value of a dt/dd kenmerken pair as an integer."""
    text = _parse_dt_dd_text(soup, label)
    if text is None:
        return None
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_dt_dd_text(soup: BeautifulSoup, label: str) -> str | None:
    """Return the dd value of a dt/dd kenmerken pair as a string, or None if absent."""
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True) == label:
            dd = dt.find_next_sibling("dd")
            if dd:
                return dd.get_text(strip=True) or None
    return None
