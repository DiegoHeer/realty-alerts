from datetime import datetime

from ninja import Schema

from scraping.models import ListingStatus, ScrapeRunStatus, Website


class ListingIn(Schema):
    website: Website
    detail_url: str
    title: str
    price: str
    city: str
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None


class ListingOut(ListingIn):
    id: int
    price_eur: int | None = None
    status: ListingStatus
    scraped_at: datetime
    created_at: datetime


class ScrapeRunOut(Schema):
    id: int
    website: Website
    started_at: datetime
    finished_at: datetime | None
    status: ScrapeRunStatus
    listings_found: int
    listings_new: int
    error_message: str | None
    duration_seconds: float | None


class ScrapeResultsIn(Schema):
    started_at: datetime
    finished_at: datetime
    error_message: str | None = None
    listings: list[ListingIn]
