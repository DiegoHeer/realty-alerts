import re
from datetime import datetime
from pathlib import PurePosixPath
from urllib.parse import urlparse, urlunparse

from bs4 import Tag
from loguru import logger

from scraper.address import parse_dutch_address, parse_dutch_postcode
from scraper.enums import Website
from scraper.models import Listing
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

    def scrape(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Pararius (since={since})")
        last_page = self._get_last_page()
        listings = []
        for page_number in range(1, last_page + 1):
            listings.extend(self._scrape_page(page_number))
        logger.info(f"Found {len(listings)} listings across {last_page} pages")
        return listings

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
            city=city or "unknown",
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
