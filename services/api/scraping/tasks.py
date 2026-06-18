import uuid

import httpx
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from loguru import logger

from scraping.cleanup import delete_expired_terminal_residences
from scraping.models import BagStatus, DetailScrapeRun, DetailScrapeRunStatus, Listing, Residence, Website
from scraping.reconciliation import reconcile_residence
from scraping.resolvers import BagLookupFailure, BagLookupSuccess, create_resolver
from scraping.resolvers.location import PdokLocationLookup
from scraping.services.ep_online import EpOnlineLookup
from scraping.resolvers.types import AddressQuery
from scraping.schemas import ScrapeDispatchPayload, ScrapeMode

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
    name="scraping.dispatch_list_scrape",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def dispatch_list_scrape(website: str, run_id: str | None = None) -> str:
    """POST a list-scrape dispatch event to the Argo Events webhook.

    Beat fires this task on a schedule defined in Django admin. Argo
    Events' webhook EventSource turns the POST into an event; the
    scraper Sensor turns the event into a one-shot K8s Job that runs
    the list scraper for the given website.
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


@shared_task(
    name="scraping.dispatch_detail_scrape",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
    rate_limit="20/m",
)
def dispatch_detail_scrape(listing_id: int, detail_scrape_run_id: int) -> str:
    listing = Listing.objects.get(pk=listing_id)
    payload = ScrapeDispatchPayload(
        website=listing.website,
        run_id=uuid.uuid4().hex,
        scrape_mode=ScrapeMode.DETAIL,
        detail_url=listing.url,
        listing_id=listing.pk,
    )

    webhook_url = settings.ARGO_EVENTS_WEBHOOK_URL
    if not webhook_url:
        logger.warning(
            "ARGO_EVENTS_WEBHOOK_URL is not set; marking detail run {} as FAILED",
            detail_scrape_run_id,
        )
        DetailScrapeRun.objects.filter(pk=detail_scrape_run_id).update(
            status=DetailScrapeRunStatus.FAILED,
            finished_at=timezone.now(),
            error_message="ARGO_EVENTS_WEBHOOK_URL not configured",
        )
        return payload.run_id

    with httpx.Client(timeout=10.0) as client:
        response = client.post(webhook_url, json=payload.model_dump(mode="json"))
        response.raise_for_status()

    logger.info(
        "Dispatched detail scrape for listing {} (run_id={})",
        listing_id,
        payload.run_id,
    )
    return payload.run_id


def _dispatch_detail_scrapes(listings) -> int:
    dispatched = 0
    for listing in listings:
        run = DetailScrapeRun.objects.create(
            listing=listing,
            website=listing.website,
            status=DetailScrapeRunStatus.DISPATCHED,
        )
        dispatch_detail_scrape.delay(listing_id=listing.pk, detail_scrape_run_id=run.pk)
        dispatched += 1
    return dispatched


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
    rate_limit="20/s",
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

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        result = resolver.resolve(
            AddressQuery(
                postcode=listing.postcode,
                house_number=listing.house_number,
                house_letter=listing.house_letter,
                house_number_suffix=listing.house_number_suffix,
                street=listing.street,
                city=listing.city,
            )
        )

    if isinstance(result, BagLookupSuccess):
        residence, _ = Residence.objects.get_or_create(
            bag_id=result.bag_id,
            defaults=_residence_defaults_from_lookup(result, listing),
        )
        _enrich_residence(residence)

        listing.residence = residence
        listing.bag_status = BagStatus.RESOLVED
        listing.bag_resolved_at = timezone.now()
        listing.save(update_fields=["residence", "bag_status", "bag_resolved_at"])
        reconcile_residence(residence)
        return

    listing.bag_status = _FAILURE_TO_BAG_STATUS[result]
    listing.bag_failure_reason = f"BAG lookup: {result.value}"
    listing.save(update_fields=["bag_status", "bag_failure_reason"])


def _enrich_residence(residence: Residence) -> None:
    needs_coordinates = residence.latitude is None or residence.longitude is None
    needs_neighbourhood = residence.neighbourhood is None
    if needs_coordinates or needs_neighbourhood:
        _enrich_location(residence)
    if residence.building_type is None:
        _enrich_building_details(residence)


def _enrich_location(residence: Residence) -> None:
    with PdokLocationLookup() as lookup:
        result = lookup.lookup(bag_id=residence.bag_id)
    if result is None:
        return

    update_fields: list[str] = []
    if residence.latitude is None or residence.longitude is None:
        residence.latitude = result.latitude
        residence.longitude = result.longitude
        update_fields += ["latitude", "longitude"]
    if residence.neighbourhood is None and result.neighbourhood is not None:
        residence.neighbourhood = result.neighbourhood
        residence.district = result.district
        update_fields += ["neighbourhood", "district"]
    if update_fields:
        residence.save(update_fields=update_fields)


def _enrich_building_details(residence: Residence) -> None:
    if not residence.postcode or not residence.house_number:
        logger.debug("EP-Online enrichment skipped for residence {}: missing postcode or house_number", residence.pk)
        return

    with EpOnlineLookup(api_key=settings.EP_ONLINE_API_KEY) as lookup:
        result = lookup.lookup(
            postcode=residence.postcode,
            house_number=residence.house_number,
            house_letter=residence.house_letter,
            house_number_suffix=residence.house_number_suffix,
        )
    if result is None:
        return

    update_fields: list[str] = []
    if result.building_type is not None:
        residence.building_type = result.building_type
        update_fields.append("building_type")
    if result.energy_label is not None:
        residence.energy_label = result.energy_label
        update_fields.append("energy_label")
    if result.energy_label_valid_until is not None:
        residence.energy_label_valid_until = result.energy_label_valid_until
        update_fields.append("energy_label_valid_until")
    if update_fields:
        residence.save(update_fields=update_fields)
        logger.info(
            "EP-Online enrichment for residence {}: building_type={}, energy_label={}",
            residence.pk,
            result.building_type,
            result.energy_label,
        )


@shared_task(name="scraping.enrich_building_details", rate_limit="10/s")
def enrich_building_details(residence_id: int) -> None:
    try:
        residence = Residence.objects.get(pk=residence_id)
    except Residence.DoesNotExist:
        return
    if not residence.postcode or not residence.house_number:
        return

    with EpOnlineLookup(api_key=settings.EP_ONLINE_API_KEY) as lookup:
        result = lookup.lookup(
            postcode=residence.postcode,
            house_number=residence.house_number,
            house_letter=residence.house_letter,
            house_number_suffix=residence.house_number_suffix,
        )
    if result is None:
        return

    update_fields: list[str] = []
    if result.building_type is not None:
        residence.building_type = result.building_type
        update_fields.append("building_type")
    if result.energy_label is not None:
        residence.energy_label = result.energy_label
        update_fields.append("energy_label")
    if result.energy_label_valid_until is not None:
        residence.energy_label_valid_until = result.energy_label_valid_until
        update_fields.append("energy_label_valid_until")
    if update_fields:
        residence.save(update_fields=update_fields)
        logger.info(
            "EP-Online enrichment for residence {}: building_type={}, energy_label={}",
            residence.pk,
            result.building_type,
            result.energy_label,
        )


@shared_task(name="scraping.enrich_location", rate_limit="20/s")
def enrich_location(residence_id: int) -> None:
    try:
        residence = Residence.objects.get(pk=residence_id)
    except Residence.DoesNotExist:
        return
    with PdokLocationLookup() as lookup:
        result = lookup.lookup(bag_id=residence.bag_id)
    if result is None:
        return

    residence.latitude = result.latitude
    residence.longitude = result.longitude
    residence.neighbourhood = result.neighbourhood
    residence.district = result.district
    residence.save(update_fields=["latitude", "longitude", "neighbourhood", "district"])
    logger.info(
        "PDOK enrichment for residence {}: lat={}, lon={}, neighbourhood={}",
        residence.pk,
        result.latitude,
        result.longitude,
        result.neighbourhood,
    )


def _residence_defaults_from_lookup(result: BagLookupSuccess, listing: Listing) -> dict:
    return {
        "city": result.city,
        "street": result.street,
        "house_number": result.house_number,
        "house_letter": result.house_letter,
        "house_number_suffix": result.house_number_suffix,
        "postcode": result.postcode,
        "current_status": listing.status,
        "status_changed_at": timezone.now(),
        "last_scraped_at": listing.list_scraped_at,
    }
