from bs4 import BeautifulSoup

from scraper.protocols import FetchStrategy


class ScrapingException(Exception):
    pass


class BaseScraper:
    """Common utilities for all scrapers."""

    def __init__(self, fetch: FetchStrategy) -> None:
        self.fetch = fetch

    def get_soup(self, url: str) -> BeautifulSoup:
        content = self.fetch.fetch(url)
        if self.is_scraping_detected(content):
            raise ScrapingException(f"Scraping detected at: {url}")
        return BeautifulSoup(content, features="html.parser")

    def is_scraping_detected(self, content: str) -> bool:
        return False
