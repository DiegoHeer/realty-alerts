from datetime import datetime

from sqlmodel import SQLModel

from app.enums import ListingStatus, Website


class ListingCreate(SQLModel):
    website: Website
    detail_url: str
    title: str
    price: str
    city: str
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None


class ListingRead(ListingCreate):
    id: int
    price_cents: int | None = None
    status: ListingStatus
    scraped_at: datetime
    created_at: datetime
