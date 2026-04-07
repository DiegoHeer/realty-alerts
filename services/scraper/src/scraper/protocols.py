from datetime import datetime
from typing import Protocol

from scraper.enums import Website
from scraper.models import Listing


class FetchStrategy(Protocol):
    def fetch(self, url: str) -> str: ...


class Scraper(Protocol):
    website: Website

    def scrape(self, since: datetime | None) -> list[Listing]: ...
