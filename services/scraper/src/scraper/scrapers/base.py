from bs4 import BeautifulSoup

from scraper.protocols import FetchStrategy


class ScrapingException(Exception):
    pass


class BaseScraper:
    """Common utilities for all scrapers."""

    # Site-specific substrings that, if present in a 200-OK body, indicate a
    # block / interstitial page. Subclasses override with confirmed markers.
    detection_markers: tuple[str, ...] = ()

    def __init__(self, fetch: FetchStrategy) -> None:
        self.fetch = fetch

    def get_soup(self, url: str) -> BeautifulSoup:
        content = self.fetch.fetch(url)
        if self.is_scraping_detected(content):
            raise ScrapingException(f"Scraping detected at: {url}")
        return BeautifulSoup(content, features="html.parser")

    def is_scraping_detected(self, content: str) -> bool:
        return any(marker in content for marker in self.detection_markers)
