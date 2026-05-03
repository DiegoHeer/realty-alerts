import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.db import OperationalError, connection, transaction
from loguru import logger
from ninja import NinjaAPI, Router, Schema
from ninja.responses import Status
from ninja.security import APIKeyHeader

from scraping.models import DeadListing, Listing, ListingUrl, ScrapeRun, ScrapeRunStatus, Website
from scraping.schemas import DeadListingIn, ListingIn, ScrapeResultsIn, ScrapeRunOut

# Fields to fill on existing listings only when the stored value is NULL.
# We treat 0 / "" as real values, not blanks — bedrooms=0 (studio) and
# area_sqm=0.0 (junk parse) are distinct from "we never had this column set".
# Volatile fields (price, scraped_at) are always overwritten — see the upsert
# below. `city` is intentionally absent: it's NOT NULL and set on create, so
# there's nothing to complement.
_COMPLEMENT_FIELDS = (
    "title",
    "street",
    "house_number",
    "house_letter",
    "house_number_suffix",
    "postcode",
    "property_type",
    "bedrooms",
    "area_sqm",
    "image_url",
)


class HealthOut(Schema):
    status: str


class InternalApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        if key and hmac.compare_digest(key, settings.REALTY_API_KEY):
            return key
        return None


api = NinjaAPI(title="Realty Alerts API", version="1.0")


@api.get("/healthz", auth=None, response=HealthOut)
def healthz(request):
    return {"status": "ok"}


@api.get("/readyz", auth=None, response={200: HealthOut, 503: HealthOut})
def readyz(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Status(503, {"status": "unavailable"})
    return {"status": "ok"}


internal_router = Router()


@internal_router.get("/scrape-runs/{website}/last-successful", response=ScrapeRunOut | None)
def get_last_successful_run(request, website: Website):
    return ScrapeRun.objects.filter(website=website, status=ScrapeRunStatus.SUCCESS).order_by("-started_at").first()


@internal_router.get("/scrape-runs/active", response=list[ScrapeRunOut])
def get_active_runs(request):
    return list(ScrapeRun.objects.filter(status=ScrapeRunStatus.RUNNING))


@internal_router.post("/scrape-runs/{website}/results", response=ScrapeRunOut)
def submit_scrape_results(request, website: Website, payload: ScrapeResultsIn):
    deduped = _dedup_by_bag_id(payload.listings)

    now = datetime.now(UTC)
    duration = (payload.finished_at - payload.started_at).total_seconds()
    run_status = ScrapeRunStatus.FAILED if payload.error_message else ScrapeRunStatus.SUCCESS

    with transaction.atomic():
        new_properties_count, new_listing_urls_count = _ingest_listings(deduped, scraped_at=now)
        _upsert_dead_listings(payload.dead_listings, scraped_at=now)

        scrape_run = ScrapeRun.objects.create(
            website=website,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            status=run_status,
            listings_found=len(payload.listings),
            new_properties_count=new_properties_count,
            new_listing_urls_count=new_listing_urls_count,
            error_message=payload.error_message,
            duration_seconds=duration,
        )

    logger.info(
        f"Scrape run for {website}: {new_properties_count} new properties / "
        f"{new_listing_urls_count} new urls / {len(payload.listings)} found, "
        f"{len(payload.dead_listings)} dead in {duration:.1f}s"
    )
    return scrape_run


def _dedup_by_bag_id(listings: list[ListingIn]) -> list[ListingIn]:
    """Keep the first occurrence of each bag_id within a single payload.
    A single scrape can surface the same property twice (duplicate cards on a
    results page); collapse on bag_id so we don't fight ourselves on the upsert.
    """
    seen: dict[str, ListingIn] = {}
    for item in listings:
        seen.setdefault(item.bag_id, item)
    return list(seen.values())


def _ingest_listings(listings: list[ListingIn], *, scraped_at: datetime) -> tuple[int, int]:
    """Upsert listings, returning (new_properties_count, new_listing_urls_count).

    The "existing" snapshot is taken before any writes so newly-created rows
    aren't counted as pre-existing.
    """
    payload_bag_ids = {item.bag_id for item in listings}
    payload_urls = {item.detail_url for item in listings}
    existing_bag_ids = set(Listing.objects.filter(bag_id__in=payload_bag_ids).values_list("bag_id", flat=True))
    existing_urls = set(ListingUrl.objects.filter(url__in=payload_urls).values_list("url", flat=True))

    for item in listings:
        _upsert_listing(item, scraped_at=scraped_at)

    return len(payload_bag_ids - existing_bag_ids), len(payload_urls - existing_urls)


def _upsert_listing(item: ListingIn, *, scraped_at: datetime) -> Listing:
    listing, created = Listing.objects.get_or_create(
        bag_id=item.bag_id,
        defaults=_listing_defaults(item, scraped_at=scraped_at),
    )
    if not created:
        _apply_listing_update(listing, item, scraped_at=scraped_at)

    # If the URL is already attached to a different Listing (e.g. a parser fix
    # changed the BAG match across runs), keep the existing FK. Re-wiring URLs
    # between listings is intentionally a manual /admin operation, not the
    # auto-ingest path.
    ListingUrl.objects.get_or_create(
        url=item.detail_url,
        defaults={"listing": listing, "website": item.website},
    )
    return listing


def _listing_defaults(item: ListingIn, *, scraped_at: datetime) -> dict:
    return {
        "title": item.title,
        "price": item.price,
        "price_eur": _parse_price_eur(item.price),
        "city": item.city,
        "street": item.street,
        "house_number": item.house_number,
        "house_letter": item.house_letter,
        "house_number_suffix": item.house_number_suffix,
        "postcode": item.postcode,
        "property_type": item.property_type,
        "bedrooms": item.bedrooms,
        "area_sqm": item.area_sqm,
        "image_url": item.image_url,
        "status": item.status,
        "scraped_at": scraped_at,
    }


# TODO: figure out a more elegant way of doing this
def _apply_listing_update(listing: Listing, item: ListingIn, *, scraped_at: datetime) -> None:
    # Always-update fields: capture price drops, status transitions, and freshness.
    listing.price = item.price
    listing.price_eur = _parse_price_eur(item.price)
    listing.status = item.status
    listing.scraped_at = scraped_at
    # Complement-only fields: fill columns currently NULL but never
    # overwrite a value that's already present (including 0 / "").
    for field in _COMPLEMENT_FIELDS:
        if getattr(listing, field) is None and (incoming := getattr(item, field)) is not None:
            setattr(listing, field, incoming)
    listing.save()


def _upsert_dead_listings(dead: list[DeadListingIn], *, scraped_at: datetime) -> None:
    """Re-categorisation is allowed across runs (e.g. a typo source that gets
    fixed and now matches BAG would be removed from listings on next ingest;
    if it's still broken we just refresh the row's reason and timestamp).

    URLs already attached to a real `Listing` are skipped — they were promoted
    out of the DLQ via /admin and shouldn't bounce back when BAG resolution
    keeps failing upstream in the scraper.
    """
    if not dead:
        return

    urls = [item.detail_url for item in dead]
    promoted_urls = set(ListingUrl.objects.filter(url__in=urls).values_list("url", flat=True))

    for item in dead:
        if item.detail_url in promoted_urls:
            continue

        DeadListing.objects.update_or_create(
            detail_url=item.detail_url,
            defaults=_dead_listing_defaults(item, scraped_at=scraped_at),
        )


def _dead_listing_defaults(item: DeadListingIn, *, scraped_at: datetime) -> dict:
    return {
        "website": item.website,
        "title": item.title,
        "price": item.price,
        "city": item.city,
        "street": item.street,
        "house_number": item.house_number,
        "house_letter": item.house_letter,
        "house_number_suffix": item.house_number_suffix,
        "postcode": item.postcode,
        "image_url": item.image_url,
        "reason": item.reason,
        "scraped_at": scraped_at,
    }


api.add_router("/internal/v1", internal_router, auth=InternalApiKey())


def _parse_price_eur(price_str: str) -> int | None:
    """Extract whole-euro value from Dutch price strings like '€ 350.000 k.k.' or '€ 1.250.000 v.o.n.'.

    Dutch numerals: '.' is thousands separator, ',' is decimal. Cent-precision is dropped.
    """
    cleaned = price_str.replace("€", "").replace("k.k.", "").replace("v.o.n.", "")
    cleaned = "".join(cleaned.split())  # drop all whitespace, including U+00A0
    if "," in cleaned:
        cleaned = cleaned.split(",", 1)[0]
    cleaned = cleaned.replace(".", "")
    try:
        return int(cleaned)
    except ValueError:
        return None
