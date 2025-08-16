from pathlib import PurePosixPath
from urllib.parse import urlparse, urlunparse

from bs4 import BeautifulSoup, ResultSet, Tag

from enums import ScrapeStrategy, Websites
from models import QueryResult
from scraper.base import BaseScraper


class ParariusScraper(BaseScraper):
    website = Websites.PARARIUS
    scrape_strategy = ScrapeStrategy.REQUESTS

    def get_query_results(self) -> list[QueryResult]:
        range_stop = self._get_last_page() + 1
        return [result for page_number in range(1, range_stop) for result in self.get_page_results(page_number)]

    def _get_last_page(self) -> int:
        soup = self.get_url_soup(self.query_url)

        anchors = soup.select('ul[class="pagination__list"] li a')
        anchor_inner_texts: list[str] = [anchor.text for anchor in anchors]

        page_numbers = [int(text) for text in anchor_inner_texts if text.isdigit()]
        max_page_number = max(page_numbers) if page_numbers else 1

        return min(max_page_number, self.max_listing_page_number)

    def get_page_results(self, page_number) -> list[QueryResult]:
        page_url = self._append_page_number_to_url(self.query_url, page_number)
        page_soup = self.get_url_soup(page_url)

        listing_cards = self._extract_listing_cards(page_soup)
        return [self._get_query_result_per_listing_card(listing_card) for listing_card in listing_cards]

    @staticmethod
    def _append_page_number_to_url(url: str, page_number: int) -> str:
        parsed_url = urlparse(url)
        new_path = PurePosixPath(parsed_url.path) / f"page-{page_number}"
        return urlunparse(parsed_url._replace(path=str(new_path)))

    def _extract_listing_cards(self, page_soup: BeautifulSoup) -> ResultSet[Tag]:
        return page_soup.select("section.listing-search-item--for-sale")

    def _get_query_result_per_listing_card(self, listing_card) -> QueryResult:
        return QueryResult(
            detail_url=self._get_detail_url_from_card(listing_card),
            title=self._get_title_from_card(listing_card),
            price=self._get_price_from_card(listing_card),
            image_url=self._get_image_url_from_card(listing_card),
        )

    def _get_detail_url_from_card(self, listing_card: Tag) -> str:
        url_element = listing_card.select_one("a.listing-search-item__link")
        return "" if url_element is None else f"https://{self.website.value}{url_element.get('href')}"

    @staticmethod
    def _get_title_from_card(listing_card: Tag) -> str:
        title_element = listing_card.select_one("h2.listing-search-item__title a")
        return "" if title_element is None else title_element.get_text().strip()

    @staticmethod
    def _get_price_from_card(listing_card: Tag) -> str:
        price_element = listing_card.select_one("div.listing-search-item__price")
        return "" if price_element is None else price_element.get_text().strip()

    @staticmethod
    def _get_image_url_from_card(listing_card: Tag) -> str:
        if image_element := listing_card.select_one("img.picture__image"):
            return str(image_element.get("src")) or ""
        return ""

    def is_scraping_detected(self, content) -> bool:
        # NOTE: Pararius doesn't have a scraping detection system in place
        return super().is_scraping_detected(content)
