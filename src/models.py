from cron_validator import CronValidator
from pydantic import BaseModel, field_validator

from enums import HouseTypes, Websites


class RealtyFilters(BaseModel):
    house_type: HouseTypes


class RealtyQuery(BaseModel):
    cron_schedule: str
    website: Websites
    filters: RealtyFilters

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
