import uuid
from datetime import datetime

from sqlmodel import Field, SQLModel


class UserFilter(SQLModel, table=True):
    __tablename__ = "user_filters"

    id: int | None = Field(default=None, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user_profiles.id")
    name: str
    city: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    property_type: str | None = None
    min_bedrooms: int | None = None
    min_area_sqm: float | None = None
    websites: list[str] = Field(default_factory=list, sa_type=None)  # TODO: configure as PG array
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
