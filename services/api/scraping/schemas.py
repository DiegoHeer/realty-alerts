from datetime import datetime
from typing import Annotated, Self

from ninja import Schema
from pydantic import StringConstraints, model_validator

from scraping.models import ListingStatus, ScrapeRunStatus, Website

# Mirrors Listing.image_url = URLField(max_length=500). Reject non-http(s) values
# (e.g. data: URIs from scraper bugs) at the schema layer so the failure is a
# 422 from Ninja rather than a Postgres DataError surfacing as a 500.
ImageUrl = Annotated[str, StringConstraints(max_length=500, pattern=r"^https?://")]


class ListingIn(Schema):
    website: Website
    detail_url: str
    title: str
    price: str
    city: str
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: ImageUrl | None = None


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

    @model_validator(mode="after")
    def _check_timestamps(self) -> Self:
        if self.finished_at < self.started_at:
            raise ValueError("finished_at must be >= started_at")
        return self


class ScrapeDispatchPayload(Schema):
    """Body posted to the Argo Events webhook to spawn a scrape Job."""

    website: Website
    run_id: str
