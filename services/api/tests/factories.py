from datetime import UTC, datetime, timedelta

import factory
from factory.django import DjangoModelFactory

from scraping.models import (
    DeadResidence,
    DeadResidenceReason,
    Listing,
    ListingStatus,
    Residence,
    ScrapeRun,
    ScrapeRunStatus,
    Website,
)


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


class ListingFactory(DjangoModelFactory):
    class Meta:
        model = Listing

    residence = factory.SubFactory(ResidenceFactory)
    website = Website.FUNDA
    url = factory.Sequence(lambda n: f"https://example.com/listing/{n}")


class DeadResidenceFactory(DjangoModelFactory):
    class Meta:
        model = DeadResidence

    website = Website.FUNDA
    detail_url = factory.Sequence(lambda n: f"https://example.com/dead/{n}")
    title = factory.Sequence(lambda n: f"Dead residence {n}")
    price = "€ 250.000 k.k."
    city = "Amsterdam"
    reason = DeadResidenceReason.BAG_NO_MATCH
    scraped_at = factory.LazyFunction(lambda: datetime.now(UTC))


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
