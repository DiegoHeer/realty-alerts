from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, Playwright

from enums import Websites
from models import QueryResult, RealtyQuery


class ScrapingException(Exception):
    pass


class BaseScraper(ABC):
    website: Websites

    def __init__(self, playwright: Playwright, realty_query: RealtyQuery) -> None:
        self.query_name = realty_query.name
        self.query_url = realty_query.query_url
        self.max_listing_page_number = realty_query.max_listing_page_number
        self.browser = self._create_browser(playwright)

    @staticmethod
    def _create_browser(playwright: Playwright) -> Browser:
        return playwright.firefox.launch()

    def get_query_results(self) -> list[QueryResult]:
        detail_urls = self.scrape_detail_urls_of_listing_page()
        return [self.scrape_detail_page(url) for url in detail_urls]

    @abstractmethod
    def scrape_detail_urls_of_listing_page(self) -> set[str]:
        pass

    @abstractmethod
    def scrape_detail_page(self, detail_url: str) -> QueryResult:
        pass

    @staticmethod
    @abstractmethod
    def is_scraping_detected(content) -> bool:
        pass

    def get_url_soup(self, url: str) -> BeautifulSoup:
        content = self._get_url_content(url)
        if self.is_scraping_detected(content):
            raise ScrapingException(f"Scraping was detected when trying to access url: {url}")

        return BeautifulSoup(content, features="html.parser")

    def _get_url_content(self, url: str) -> str:
        page = self.browser.new_page()

        try:
            page.goto(url)
        except TimeoutError:
            raise ScrapingException(f"A timeout has occured while trying to scrape the following url: {url}")

        content = page.content()
        page.close()

        return content
