from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import Tag
from loguru import logger

from scraper.address import parse_dutch_address
from scraper.enums import Website
from scraper.models import Listing
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

    def scrape(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Vastgoed NL (since={since})")
        last_page = self._get_last_page()
        listings = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {len(listings)} listings across {last_page} pages")
        return listings

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
