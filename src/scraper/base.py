from abc import ABC, abstractmethod

from bs4 import BeautifulSoup
from playwright.sync_api import Browser, Playwright

from enums import ScrapeStrategy, Websites
from models import QueryResult, RealtyQuery
from settings import SETTINGS


class ScrapingException(Exception):
    pass


class BaseScraper(ABC):
    website: Websites
    scrape_strategy: ScrapeStrategy

    def __init__(self, playwright: Playwright, realty_query: RealtyQuery) -> None:
        self.query_name = realty_query.name
        self.query_url = realty_query.query_url
        self.max_listing_page_number = realty_query.max_listing_page_number
        self.browser = self._connect_browser(playwright)

    @staticmethod
    def _connect_browser(playwright: Playwright) -> Browser:
        return playwright.firefox.connect(SETTINGS.browser_url)

    @abstractmethod
    def get_query_results(self) -> list[QueryResult]:
        pass

    @abstractmethod
    def is_scraping_detected(self, content) -> bool:
        return False

    def get_url_soup(self, url: str) -> BeautifulSoup:
        content = self._scrape_url_content(url)
        if self.is_scraping_detected(content):
            raise ScrapingException(f"Scraping was detected when trying to access url: {url}")

        return BeautifulSoup(content, features="html.parser")

    def _scrape_url_content(self, url: str) -> str:
        page = self.browser.new_page()

        try:
            page.goto(url)
        except TimeoutError:
            raise ScrapingException(f"A timeout has occured while trying to scrape the following url: {url}")

        content = page.content()
        page.close()

        return content
