import uuid

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from loguru import logger

from scraping.cleanup import delete_expired_terminal_listings
from scraping.models import Website
from scraping.schemas import ScrapeDispatchPayload


@shared_task(name="scraping.ping")
def ping() -> str:
    return "pong"


@shared_task(
    name="scraping.dispatch_scrape",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def dispatch_scrape(website: str, run_id: str | None = None) -> str:
    """POST a scrape dispatch event to the Argo Events webhook.

    Beat fires this task on a schedule defined in Django admin. Argo
    Events' webhook EventSource turns the POST into an event; the
    scraper Sensor turns the event into a one-shot K8s Job.

    Returns the run_id (generated if not provided) so callers can
    correlate with downstream pod logs (`SCRAPE_RUN_ID` env).
    """
    payload = ScrapeDispatchPayload(
        website=Website(website),
        run_id=run_id or uuid.uuid4().hex,
    )

    webhook_url = settings.ARGO_EVENTS_WEBHOOK_URL
    if not webhook_url:
        logger.warning(
            "ARGO_EVENTS_WEBHOOK_URL is not set; skipping dispatch for {} (run_id={})",
            payload.website,
            payload.run_id,
        )
        return payload.run_id

    with httpx.Client(timeout=10.0) as client:
        response = client.post(webhook_url, json=payload.model_dump(mode="json"))
        response.raise_for_status()

    logger.info("Dispatched scrape for {} (run_id={})", payload.website, payload.run_id)
    return payload.run_id


@shared_task(name="scraping.cleanup_expired_listings")
def cleanup_expired_listings() -> int:
    """Hard-delete listings that have been in a terminal status (sold or
    sale_pending) past the TTL. Schedule via a PeriodicTask in Django admin."""
    return delete_expired_terminal_listings(now=timezone.now())
