from sqlmodel import SQLModel


class FilterCreate(SQLModel):
    name: str
    city: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    property_type: str | None = None
    min_bedrooms: int | None = None
    min_area_sqm: float | None = None
    websites: list[str] = []
    is_active: bool = True


class FilterRead(FilterCreate):
    id: int


class FilterUpdate(SQLModel):
    name: str | None = None
    city: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    property_type: str | None = None
    min_bedrooms: int | None = None
    min_area_sqm: float | None = None
    websites: list[str] | None = None
    is_active: bool | None = None
