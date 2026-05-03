from datetime import UTC, datetime, timedelta

import factory
from factory.django import DjangoModelFactory

from scraping.models import Listing, ListingStatus, ListingUrl, ScrapeRun, ScrapeRunStatus, Website


class ListingFactory(DjangoModelFactory):
    class Meta:
        model = Listing

    bag_id = factory.Sequence(lambda n: f"00032000{n:08d}")
    title = factory.Sequence(lambda n: f"Listing {n}")
    price = "€ 500.000 k.k."
    price_eur = 500_000
    city = "Amsterdam"
    property_type = "apartment"
    bedrooms = 2
    area_sqm = 75.0
    image_url = factory.Sequence(lambda n: f"https://example.com/img/{n}.jpg")
    status = ListingStatus.ACTIVE
    scraped_at = factory.LazyFunction(lambda: datetime.now(UTC))


class ListingUrlFactory(DjangoModelFactory):
    class Meta:
        model = ListingUrl

    listing = factory.SubFactory(ListingFactory)
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
    new_properties_count = 0
    new_listing_urls_count = 0
    duration_seconds = 300.0
