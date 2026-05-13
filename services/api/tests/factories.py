from datetime import UTC, datetime, timedelta

import factory
from factory.django import DjangoModelFactory

from scraping.models import ListScrapeRun, ListScrapeRunStatus, Listing, ListingStatus, Residence, Website


class ResidenceFactory(DjangoModelFactory):
    class Meta:
        model = Residence

    bag_id = factory.Sequence(lambda n: f"00032000{n:08d}")
    city = "Amsterdam"
    current_price_eur = 500_000
    current_status = ListingStatus.NEW
    status_changed_at = factory.LazyFunction(lambda: datetime.now(UTC))
    last_scraped_at = factory.LazyFunction(lambda: datetime.now(UTC))


class ListingFactory(DjangoModelFactory):
    class Meta:
        model = Listing

    residence = factory.SubFactory(ResidenceFactory)
    website = Website.FUNDA
    url = factory.Sequence(lambda n: f"https://example.com/listing/{n}")


class ListScrapeRunFactory(DjangoModelFactory):
    class Meta:
        model = ListScrapeRun

    website = Website.FUNDA
    started_at = factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(minutes=5))
    finished_at = factory.LazyFunction(lambda: datetime.now(UTC))
    status = ListScrapeRunStatus.SUCCESS
    listings_found = 0
    new_listings_count = 0
    duration_seconds = 300.0
