from datetime import datetime

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel

from enums import ListingStatus, Website
from utils import utcnow


class Listing(SQLModel, table=True):
    __tablename__ = "listings"
    __table_args__ = (
        Index("idx_listings_filters", "city", "property_type", "price_cents"),
        Index("idx_listings_website_created", "website", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    website: Website
    detail_url: str = Field(unique=True, index=True)
    title: str
    price: str
    price_cents: int | None = None
    city: str = Field(index=True)
    property_type: str | None = None
    bedrooms: int | None = None
    area_sqm: float | None = None
    image_url: str | None = None
    status: ListingStatus = ListingStatus.ACTIVE
    scraped_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
