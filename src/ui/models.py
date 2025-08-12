from urllib.parse import urljoin, urlparse

import requests
from cron_validator import CronValidator
from django.core.exceptions import ValidationError
from django.db import models
from requests import HTTPError

from enums import QueryResultStatus, Websites
from settings import SETTINGS


def _validate_ntfy_topic(value: str) -> None:
    url = urljoin(SETTINGS.ntfy_url, value)
    try:
        response = requests.get(url)
        response.raise_for_status()
    except HTTPError:
        msg = (
            f"The NTFY topic '{value}' or the base url '{SETTINGS.ntfy_url}' is invalid. "
            "Please correct the `ntfy_topic` in the query yml file (don't use spaces) "
            "or correct the environment variable NTFY_URL."
        )
        raise ValidationError(msg)


def _validate_cron_schedule(value: str) -> None:
    try:
        CronValidator.parse(value)
    except ValueError:
        msg = f"The cron schedule {value} is invalid. Please place a valid crontab."
        raise ValidationError(msg)


def _validate_query_url(value: str) -> None:
    parsed = urlparse(value)

    if not parsed.scheme or not parsed.netloc:
        msg = f"The query url {value} is invalid. Make sure to include a valid scheme (http or https) and domain."
        raise ValidationError(msg)

    VALID_DOMAINS = [item.value for item in Websites]
    if parsed.netloc not in VALID_DOMAINS:
        raise ValidationError(f"The query url {value} has an invalid domain. Accepted domains are: {VALID_DOMAINS}.")


class RealtyQuery(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    name = models.CharField(max_length=255, unique=True)
    ntfy_topic = models.CharField(max_length=255, validators=[_validate_ntfy_topic])
    cron_schedule = models.CharField(max_length=100, validators=[_validate_cron_schedule])
    query_url = models.URLField(validators=[_validate_query_url])
    max_listing_page_number = models.PositiveIntegerField(default=3)
    notify_startup_of_app = models.BooleanField(default=True)  # TODO: allow for notify testing of query in the form
    notify_if_no_new_listing = models.BooleanField(default=False)  # TODO: remove this in the future

    class Meta:
        verbose_name_plural = "realty queries"

    @property
    def website(self) -> Websites:
        parsed_url = urlparse(self.query_url)
        return Websites(parsed_url.netloc)

    @property
    def notification_url(self) -> str:
        return urljoin(SETTINGS.ntfy_url, self.ntfy_topic)

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        return super().save(*args, **kwargs)


class RealtyResult(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=QueryResultStatus.choices(), default=QueryResultStatus.NEW)
    detail_url = models.URLField()
    query = models.ForeignKey(RealtyQuery, on_delete=models.CASCADE, related_name="results")
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    image_url = models.URLField()

    def __str__(self) -> str:
        return f"{self.title} ({self.query.name})"
