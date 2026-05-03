from datetime import datetime
from typing import Protocol, Self

from scraper.enums import Website
from scraper.models import Listing


class FetchStrategy(Protocol):
    def fetch(self, url: str) -> str: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...


class Scraper(Protocol):
    website: Website

    def scrape(self, since: datetime | None) -> list[Listing]: ...
