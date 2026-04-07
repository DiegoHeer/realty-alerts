from datetime import datetime

from scraper.enums import Website
from scraper.models import Listing
from scraper.protocols import FetchStrategy


class FundaScraper:
    website = Website.FUNDA

    def __init__(self, fetch: FetchStrategy) -> None:
        self.fetch = fetch

    def scrape(self, since: datetime | None) -> list[Listing]:
        raise NotImplementedError
