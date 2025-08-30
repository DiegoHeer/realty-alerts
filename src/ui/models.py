from urllib.parse import urljoin, urlparse

import requests
from django.core.exceptions import ValidationError
from django.db import models
from requests import HTTPError

from enums import QueryResultStatus, Websites
from settings import SETTINGS
from django_celery_beat.models import PeriodicTask


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
    periodic_task = models.OneToOneField(PeriodicTask, on_delete=models.CASCADE, related_name="queries")
    query_url = models.URLField(max_length=500, validators=[_validate_query_url])
    max_listing_page_number = models.PositiveIntegerField(default=3)

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

    def __str__(self) -> str:
        return f"{self.name}"


class RealtyResult(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(choices=QueryResultStatus.choices(), default=QueryResultStatus.NEW)
    query = models.ForeignKey(RealtyQuery, on_delete=models.CASCADE, related_name="results")
    detail_url = models.URLField(max_length=500)
    title = models.CharField(max_length=500)
    price = models.CharField(max_length=100)
    image_url = models.URLField(max_length=500)

    class Meta:
        unique_together = ["query", "detail_url"]

    def __str__(self) -> str:
        return f"{self.title} ({self.query.name})"
