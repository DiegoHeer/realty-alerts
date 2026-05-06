from datetime import UTC, datetime, timedelta

import factory
from factory.django import DjangoModelFactory

from scraping.models import Listing, ListingStatus, Residence, ScrapeRun, ScrapeRunStatus, Website


class ResidenceFactory(DjangoModelFactory):
    class Meta:
        model = Residence

    bag_id = factory.Sequence(lambda n: f"00032000{n:08d}")
    title = factory.Sequence(lambda n: f"Residence {n}")
    price = "€ 500.000 k.k."
    price_eur = 500_000
    city = "Amsterdam"
    property_type = "apartment"
    bedrooms = 2
    area_sqm = 75.0
    image_url = factory.Sequence(lambda n: f"https://example.com/img/{n}.jpg")
    status = ListingStatus.NEW
    status_changed_at = factory.LazyFunction(lambda: datetime.now(UTC))
    scraped_at = factory.LazyFunction(lambda: datetime.now(UTC))
    # Mirror the same-row backfill the migration applied so factory-built
    # Residences look like real post-migration rows.
    current_price_eur = factory.SelfAttribute("price_eur")
    current_status = factory.SelfAttribute("status")
    last_scraped_at = factory.SelfAttribute("scraped_at")


class ListingFactory(DjangoModelFactory):
    class Meta:
        model = Listing

    residence = factory.SubFactory(ResidenceFactory)
    website = Website.FUNDA
    url = factory.Sequence(lambda n: f"https://example.com/listing/{n}")


class ScrapeRunFactory(DjangoModelFactory):
    class Meta:
        model = ScrapeRun

    website = Website.FUNDA
    started_at = factory.LazyFunction(lambda: datetime.now(UTC) - timedelta(minutes=5))
    finished_at = factory.LazyFunction(lambda: datetime.now(UTC))
    status = ScrapeRunStatus.SUCCESS
    listings_found = 0
    new_residences_count = 0
    new_listings_count = 0
    duration_seconds = 300.0
