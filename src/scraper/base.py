from abc import ABC, abstractmethod

from enums import Websites
from models import QueryResult


class BaseScraper(ABC):
    website: Websites

    def __init__(self, query_url: str) -> None:
        self.query_url = query_url

    @abstractmethod
    def scrape_urls_of_query_page(self, query_url: str) -> list[str]:
        pass

    def get_query_results(self, detail_urls: list[str]) -> list[QueryResult]:
        return [self._scrape_detail_page(url) for url in detail_urls]

    @abstractmethod
    def _scrape_detail_page(self, url: str) -> QueryResult:
        pass
