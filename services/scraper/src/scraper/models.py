from pydantic import BaseModel

from scraper.enums import Website


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


class DeadListing(BaseModel):
    """A listing that failed BAG enrichment terminally — pairs the scraped
    Listing with the structured reason the runner derived from the matcher's
    outcome and the listing's own input quality."""

    listing: Listing
    reason: str
