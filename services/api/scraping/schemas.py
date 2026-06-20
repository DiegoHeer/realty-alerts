from datetime import datetime
from enum import StrEnum
from typing import Annotated, Self

from ninja import Schema
from pydantic import StringConstraints, model_validator

from scraping.models import (
    BuildingType,
    DetailScrapeRunStatus,
    EnergyLabel,
    ListScrapeRunStatus,
    ListingStatus,
    Website,
)


class ScrapeMode(StrEnum):
    LIST = "list"
    DETAIL = "detail"


class DetailResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


# Mirrors Listing.image_url = URLField(max_length=2000). Reject non-http(s) values
# (e.g. data: URIs from scraper bugs) at the schema layer so the failure is a
# 422 from Ninja rather than a Postgres DataError surfacing as a 500. The 2000
# cap covers fastly/CDN signed URLs with query strings (observed up to ~700
# chars on pararius) while staying well under the de-facto browser URL limit.
ImageUrl = Annotated[str, StringConstraints(max_length=2000, pattern=r"^https?://")]

# Reject empty titles so scraper selector drift surfaces as a 422 instead of
# silently storing blank cards in Postgres.
Title = Annotated[str, StringConstraints(min_length=1)]


class ListingIn(Schema):
    website: Website
    detail_url: str
    title: Title
    price: str
    city: str
    street: str | None = None
    house_number: int | None = None
    house_letter: str | None = None
    house_number_suffix: str | None = None
    postcode: str | None = None
    image_url: ImageUrl | None = None
    status: ListingStatus = ListingStatus.NEW


class ListingOut(Schema):
    url: str
    website: Website
    image_url: str | None = None
    surface_area_m2: int | None = None
    bedroom_count: int | None = None
    bathroom_count: int | None = None
    room_count: int | None = None
    construction_period: str | None = None


class ResidenceOut(Schema):
    id: int
    bag_id: str
    city: str
    street: str | None = None
    house_number: int | None = None
    house_letter: str | None = None
    house_number_suffix: str | None = None
    postcode: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    neighbourhood: str | None = None
    district: str | None = None
    building_type: BuildingType | None = None
    energy_label: EnergyLabel | None = None
    zoning_designation: str | None = None
    soil_wbb_count: int | None = None
    current_price_eur: int | None = None
    current_status: ListingStatus
    last_scraped_at: datetime | None = None
    status_changed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    listings: list[ListingOut]


class ListScrapeRunOut(Schema):
    id: int
    website: Website
    started_at: datetime
    finished_at: datetime | None
    status: ListScrapeRunStatus
    listings_found: int
    new_listings_count: int
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
    scrape_mode: ScrapeMode = ScrapeMode.LIST
    detail_url: str | None = None
    listing_id: int | None = None


class DetailListingIn(Schema):
    price: str
    status: ListingStatus
    surface_area_m2: int | None = None
    bedroom_count: int | None = None
    bathroom_count: int | None = None
    room_count: int | None = None
    construction_period: str | None = None
    energy_label: str | None = None
    postcode: str | None = None


class DetailResultIn(Schema):
    status: DetailResultStatus
    started_at: datetime
    finished_at: datetime
    detail: DetailListingIn | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def _success_requires_detail(self) -> Self:
        if self.status == DetailResultStatus.SUCCESS and self.detail is None:
            raise ValueError("detail is required when status is 'success'")
        return self


class DetailScrapeRunOut(Schema):
    id: int
    listing_id: int
    website: Website
    status: DetailScrapeRunStatus
    dispatched_at: datetime
    finished_at: datetime | None
    error_message: str | None
    duration_seconds: float | None


class ResidenceFilters(Schema):
    city: str | None = None
    neighbourhood: str | None = None
    district: str | None = None
    street: str | None = None
    postcode: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    status: ListingStatus | None = None


class CityOut(Schema):
    code: str
    name: str


class CityStatsOut(Schema):
    code: str
    name: str
    stats: dict | None
    stats_year: int | None


class DistrictStatsOut(Schema):
    code: str
    name: str
    city_code: str
    stats: dict | None
    stats_year: int | None
    geometry: list | None = None

    @staticmethod
    def resolve_city_code(obj):
        return obj.city.code if hasattr(obj.city, "code") else obj.city_id


class NeighborhoodStatsOut(Schema):
    code: str
    name: str
    city_code: str
    district_code: str | None
    stats: dict | None
    stats_year: int | None
    geometry: list | None = None

    @staticmethod
    def resolve_city_code(obj):
        return obj.city.code if hasattr(obj.city, "code") else obj.city_id

    @staticmethod
    def resolve_district_code(obj):
        if obj.district:
            return obj.district.code if hasattr(obj.district, "code") else obj.district_id
        return None


class GeoDistrictOut(Schema):
    code: str
    name: str
    city_code: str
    geometry: list

    @staticmethod
    def resolve_city_code(obj):
        return obj.city.code if hasattr(obj.city, "code") else obj.city_id


class GeoNeighborhoodOut(Schema):
    code: str
    name: str
    city_code: str
    district_code: str | None
    geometry: list

    @staticmethod
    def resolve_city_code(obj):
        return obj.city.code if hasattr(obj.city, "code") else obj.city_id

    @staticmethod
    def resolve_district_code(obj):
        if obj.district:
            return obj.district.code if hasattr(obj.district, "code") else obj.district_id
        return None
