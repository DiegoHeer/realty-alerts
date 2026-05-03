from typing import Self

from pydantic import BaseModel

from scraper.enums import ListingStatus, Website


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
    bag_id: str | None = None
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None
    website: Website
    status: ListingStatus = ListingStatus.NEW


# Mirrors the API's DeadListingIn schema 1:1 — pre-enrichment fields
# (bag_id, property_type, bedrooms, area_sqm don't apply since these
# listings never reached enrichment).
class DeadListing(BaseModel):
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
    reason: str

    @classmethod
    def from_listing(cls, listing: Listing, reason: str) -> Self:
        return cls(
            **listing.model_dump(exclude={"bag_id", "property_type", "bedrooms", "area_sqm"}),
            reason=reason,
        )
