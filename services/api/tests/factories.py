from datetime import UTC, datetime, timedelta

import factory
from factory.django import DjangoModelFactory

from scraping.models import (
    City,
    District,
    Feedback,
    ListScrapeRun,
    ListScrapeRunStatus,
    Listing,
    ListingStatus,
    Neighborhood,
    Residence,
    Website,
)


class ResidenceFactory(DjangoModelFactory):
    class Meta:
        model = Residence

    bag_id = factory.Sequence(lambda n: f"00032000{n:08d}")
    city = "Amsterdam"
    current_price_eur = 500_000
    current_status = ListingStatus.NEW
    status_changed_at = factory.LazyFunction(lambda: datetime.now(UTC))
    last_scraped_at = factory.LazyFunction(lambda: datetime.now(UTC))
    latitude = 52.3676
    longitude = 4.8841


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


class CityFactory(DjangoModelFactory):
    class Meta:
        model = City

    code = factory.Sequence(lambda n: f"{n:04d}")
    name = factory.LazyAttribute(lambda o: f"City-{o.code}")


class DistrictFactory(DjangoModelFactory):
    class Meta:
        model = District

    code = factory.Sequence(lambda n: f"WK{n:08d}")
    name = factory.LazyAttribute(lambda o: f"District-{o.code}")
    city = factory.SubFactory(CityFactory)


class NeighborhoodFactory(DjangoModelFactory):
    class Meta:
        model = Neighborhood

    code = factory.Sequence(lambda n: f"BU{n:010d}")
    name = factory.LazyAttribute(lambda o: f"Neighborhood-{o.code}")
    city = factory.SubFactory(CityFactory)
    district = factory.SubFactory(DistrictFactory, city=factory.SelfAttribute("..city"))


class FeedbackFactory(DjangoModelFactory):
    class Meta:
        model = Feedback

    message = factory.Sequence(lambda n: f"Feedback message {n}")
