from pydantic import BaseModel

from scraper.enums import ListingStatus, Website


class DetailListing(BaseModel):
    price: str
    status: ListingStatus
    surface_area_m2: int | None = None
    bedroom_count: int | None = None
    bathroom_count: int | None = None
    room_count: int | None = None
    construction_period: str | None = None
    energy_label: str | None = None
    postcode: str | None = None


class Listing(BaseModel):
    detail_url: str
    title: str
    price: str
    city: str
    street: str | None = None
    house_number: int | None = None
    house_letter: str | None = None
    house_number_suffix: str | None = None
    postcode: str | None = None
    image_url: str | None = None
    website: Website
    status: ListingStatus = ListingStatus.NEW
