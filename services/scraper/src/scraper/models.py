from pydantic import BaseModel

from scraper.enums import Website


class Listing(BaseModel):
    detail_url: str
    title: str
    price: str
    city: str
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None
    website: Website
