from datetime import datetime

from sqlmodel import Field, SQLModel

from app.enums import ListingStatus, Website


class Listing(SQLModel, table=True):
    __tablename__ = "listings"

    id: int | None = Field(default=None, primary_key=True)
    website: Website
    detail_url: str = Field(unique=True, index=True)
    title: str
    price: str
    city: str
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None
    status: ListingStatus = ListingStatus.ACTIVE
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
