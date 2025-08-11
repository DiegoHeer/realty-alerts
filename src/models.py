from typing import Annotated
from urllib.parse import urljoin, urlparse

import requests
from cron_validator import CronValidator
from pydantic import BaseModel, Field, field_validator
from requests import HTTPError

from enums import Websites
from settings import SETTINGS


# TODO: when the Django UI is working, this model should be deleted
class RealtyQuery(BaseModel):
    name: str
    ntfy_topic: str
    cron_schedule: str
    query_url: str
    max_listing_page_number: Annotated[int, Field(strict=True, ge=0)] = 3
    notify_startup_of_app: bool = True
    notify_if_no_new_listing: bool = False

    @property
    def website(self) -> Websites:
        parsed_url = urlparse(self.query_url)
        return Websites(parsed_url.netloc)

    @property
    def notification_url(self) -> str:
        return urljoin(SETTINGS.ntfy_url, self.ntfy_topic)

    @field_validator("cron_schedule")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        try:
            CronValidator.parse(value)
        except ValueError:
            msg = f"The cron schedule {value} is invalid. Please place a valid crontab."
            raise ValueError(msg)

        return value

    @field_validator("ntfy_topic")
    @classmethod
    def validate_ntfy_topic(cls, value: str) -> str:
        url = urljoin(SETTINGS.ntfy_url, value)
        try:
            response = requests.get(url)
            response.raise_for_status()
        except HTTPError:
            msg = (
                f"The NTFY topic {value} or the base url {SETTINGS.ntfy_url} is invalid. "
                "Please correct the `ntfy_topic` in the query yml file (don't use spaces) "
                "or correct the environment variable NTFY_URL."
            )
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


# TODO: when the Django UI is working, this model should be deleted
class QueryResult(BaseModel):
    detail_url: str
    query_name: str
    title: str
    price: str
    image_url: str
