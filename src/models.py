from typing import Annotated
from urllib.parse import urlparse

from cron_validator import CronValidator
from pydantic import BaseModel, Field, field_validator

from enums import Websites


class RealtyQuery(BaseModel):
    cron_schedule: str
    query_url: str
    max_listing_page_number: Annotated[int, Field(strict=True, ge=0, le=5)] = 3  # TODO: explain why this limit

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        try:
            CronValidator.parse(value)
        except ValueError:
            msg = f"The cron schedule {value} is invalid. Please place a valid crontab."
            raise ValueError(msg)

        return value

    @field_validator("query_url")
    @classmethod
    def validate_query_url(cls, value: str):
        parsed = urlparse(value)

        if not parsed.scheme or not parsed.netloc:
            msg = f"The query url {value} is invalid. Make sure to include a valid scheme (http or https) and domain."
            raise ValueError(msg)

        VALID_DOMAINS = [item.value for item in Websites]
        if parsed.netloc not in VALID_DOMAINS:
            raise ValueError(f"The query url {value} has an invalid domain. Accepted domains are: {VALID_DOMAINS}.")

        return value


class QueryResult(BaseModel):
    detail_url: str
    title: str
    price: str
    image_url: str
