from cron_validator import CronValidator
from pydantic import BaseModel, field_validator

from enums import ConstructionPeriod, ConstructionType, EnergyLabel, HouseTypes, Websites


class QueryFilter(BaseModel):
    house_types: list[HouseTypes] | None = None
    energy_labels: list[EnergyLabel] | None = None
    construction_types: list[ConstructionType] | None = None
    construction_periods: list[ConstructionPeriod] | None = None
    min_price: int | None = None
    max_price: int | None = None
    min_floor_area: int | None = None
    max_floor_area: int | None = None
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_bedrooms: int | None = None
    max_bedrooms: int | None = None


class RealtyQuery(BaseModel):
    cron_schedule: str
    website: Websites
    filters: QueryFilter

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        try:
            CronValidator.parse(value)
        except ValueError:
            msg = f"The cron schedule {value} is invalid. Please place a valid crontab."
            raise ValueError(msg)

        return value


class QueryResult(BaseModel):
    url: str
    title: str
