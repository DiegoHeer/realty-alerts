import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, VARCHAR
from sqlmodel import Field, SQLModel

from app.utils import utcnow


class UserFilter(SQLModel, table=True):
    __tablename__ = "user_filters"

    id: int | None = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user_profiles.id", index=True)
    name: str
    city: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    property_type: str | None = None
    min_bedrooms: int | None = None
    min_area_sqm: float | None = None
    websites: list[str] = Field(default_factory=list, sa_column=Column(ARRAY(VARCHAR)))
    is_active: bool = True
    created_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    updated_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
