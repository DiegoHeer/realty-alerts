import uuid

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from loguru import logger

from scraping.bag_client import BagClient, BagLookupFailure, BagLookupSuccess
from scraping.cleanup import delete_expired_terminal_residences
from scraping.models import BagStatus, Listing, Residence, Website
from scraping.reconciliation import reconcile_residence
from scraping.schemas import ScrapeDispatchPayload

# BagLookupFailure → BagStatus. The client's MISSING_ADDRESS short-circuits
# before any HTTP call (postcode/house_number missing); NO_MATCH and
# AMBIGUOUS come back from the API.
_FAILURE_TO_BAG_STATUS = {
    BagLookupFailure.MISSING_ADDRESS: BagStatus.MISSING_ADDRESS,
    BagLookupFailure.NO_MATCH: BagStatus.BAG_NO_MATCH,
    BagLookupFailure.AMBIGUOUS: BagStatus.BAG_AMBIGUOUS,
}


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


@shared_task(name="scraping.cleanup_expired_residences")
def cleanup_expired_residences() -> int:
    """Hard-delete residences that have been in a terminal status (sold or
    sale_pending) past the TTL. Schedule via a PeriodicTask in Django admin."""
    return delete_expired_terminal_residences(now=timezone.now())


@shared_task(
    name="scraping.resolve_bag",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=5,
    rate_limit="5/s",
)
def resolve_bag(listing_id: int) -> None:
    """Resolve a Listing's raw address bits to a BAG-canonical Residence.

    Idempotent: re-runs are safe and skip listings that have already
    transitioned out of `pending`. HTTPError raises for Celery retry; any
    terminal BAG outcome (no-match / ambiguous / missing-address) writes
    `bag_status` and `bag_failure_reason` and returns without retrying."""
    listing = Listing.objects.filter(pk=listing_id).first()
    if listing is None or listing.bag_status != BagStatus.PENDING:
        return

    with BagClient(api_key=settings.BAG_API_KEY) as client:
        result = client.lookup(
            postcode=listing.postcode,
            house_number=listing.house_number,
            house_letter=listing.house_letter,
            house_number_suffix=listing.house_number_suffix,
        )

    if isinstance(result, BagLookupSuccess):
        residence, _ = Residence.objects.get_or_create(
            bag_id=result.bag_id,
            defaults=_residence_defaults_from_lookup(result, listing),
        )
        listing.residence = residence
        listing.bag_status = BagStatus.RESOLVED
        listing.bag_resolved_at = timezone.now()
        listing.save(update_fields=["residence", "bag_status", "bag_resolved_at"])
        reconcile_residence(residence)
        return

    listing.bag_status = _FAILURE_TO_BAG_STATUS[result]
    listing.bag_failure_reason = f"BAG lookup: {result.value}"
    listing.save(update_fields=["bag_status", "bag_failure_reason"])


def _residence_defaults_from_lookup(result: BagLookupSuccess, listing: Listing) -> dict:
    now = timezone.now()
    return {
        "title": listing.title or "",
        "price": listing.price or "",
        "price_eur": listing.price_eur,
        "city": result.city,
        "street": result.street,
        "house_number": result.house_number,
        "house_letter": result.house_letter,
        "house_number_suffix": result.house_number_suffix,
        "postcode": result.postcode,
        "image_url": listing.image_url,
        "status": listing.status,
        "status_changed_at": now,
        "scraped_at": listing.scraped_at or now,
        "current_status": listing.status,
        "last_scraped_at": listing.scraped_at,
    }
