from datetime import datetime
from typing import Protocol, Self

from scraper.enums import Website
from scraper.models import DetailListing, Listing


class FetchStrategy(Protocol):
    def fetch(self, url: str) -> str: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...


class ListScraper(Protocol):
    website: Website

    def scrape_list(self, since: datetime | None) -> list[Listing]: ...


class DetailScraper(Protocol):
    website: Website

    def scrape_detail(self, url: str) -> DetailListing: ...
