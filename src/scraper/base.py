from abc import ABC, abstractmethod

from enums import Websites
from models import QueryFilter, QueryResult


class BaseScraper(ABC):
    website: Websites
    base_url: str

    def __init__(self, query_filter: QueryFilter) -> None:
        self.filter = query_filter

    @abstractmethod
    def build_query_url(self) -> str:
        pass

    @abstractmethod
    def scrape_urls_of_query_page(self, query_url: str) -> list[str]:
        pass

    def get_query_results(self, detail_urls: list[str]) -> list[QueryResult]:
        return [self._scrape_detail_page(url) for url in detail_urls]

    @abstractmethod
    def _scrape_detail_page(self, url: str) -> QueryResult:
        pass
