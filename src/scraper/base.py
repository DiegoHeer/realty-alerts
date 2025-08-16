from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import Browser, Playwright

from enums import ScrapeStrategy, Websites
from models import QueryResult
from settings import SETTINGS


class ScrapingException(Exception):
    pass


class BaseScraper(ABC):
    website: Websites
    scrape_strategy: ScrapeStrategy

    def __init__(self, playwright: Playwright, query_name: str, query_url: str, max_listing_page_number: int) -> None:
        self.query_name = query_name
        self.query_url = query_url
        self.max_listing_page_number = max_listing_page_number
        self.playwright = playwright

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
        mapping = {
            ScrapeStrategy.PLAYWRIGHT: self._scrape_content_with_playwright,
            ScrapeStrategy.REQUESTS: self._scrape_url_content_with_requests,
        }

        scrape_function = mapping[self.scrape_strategy]
        return scrape_function(url)

    def _scrape_content_with_playwright(self, url: str) -> str:
        if not hasattr(self, "browser"):
            self.browser = self._connect_browser(self.playwright)

        page = self.browser.new_page()

        try:
            page.goto(url, wait_until="domcontentloaded")
        except TimeoutError:
            raise ScrapingException(f"A timeout has occured while trying to scrape the following url: {url}")

        content = page.content()
        page.close()

        return content

    @staticmethod
    def _connect_browser(playwright: Playwright) -> Browser:
        return playwright.firefox.connect(SETTINGS.browser_url)

    def _scrape_url_content_with_requests(self, url: str) -> str:
        try:
            response = requests.get(url)  # This is less resource intensive than Playwright
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise ScrapingException(f"Failed to scrape the following url: {url}. Exception: {exc}")

        return response.text
