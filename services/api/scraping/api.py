import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.db import OperationalError, connection, transaction
from django.utils import timezone
from loguru import logger
from ninja import NinjaAPI, Router, Schema
from ninja.responses import Status
from ninja.security import APIKeyHeader

from scraping.models import BagStatus, Listing, Residence, ScrapeRun, ScrapeRunStatus, Website
from scraping.reconciliation import reconcile_residence
from scraping.schemas import ResidenceIn, ScrapeResultsIn, ScrapeRunOut
from scraping.tasks import resolve_bag

# Fields to fill on existing residences only when the stored value is NULL.
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
    legacy_items, pending_items = _split_by_bag_id(payload.listings)
    deduped_legacy = _dedup_by_bag_id(legacy_items)

    now = datetime.now(UTC)
    duration = (payload.finished_at - payload.started_at).total_seconds()
    run_status = ScrapeRunStatus.FAILED if payload.error_message else ScrapeRunStatus.SUCCESS

    with transaction.atomic():
        new_residences_count, legacy_new_count = _ingest_residences(deduped_legacy, scraped_at=now)
        pending_new_count = _ingest_pending_listings(pending_items, scraped_at=now)

        new_listings_count = legacy_new_count + pending_new_count
        scrape_run = ScrapeRun.objects.create(
            website=website,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            status=run_status,
            listings_found=len(payload.listings),
            new_residences_count=new_residences_count,
            new_listings_count=new_listings_count,
            error_message=payload.error_message,
            duration_seconds=duration,
        )

    logger.info(
        f"Scrape run for {website}: {new_residences_count} new residences / "
        f"{new_listings_count} new listings / {len(payload.listings)} found "
        f"in {duration:.1f}s"
    )
    return scrape_run


def _split_by_bag_id(items: list[ResidenceIn]) -> tuple[list[ResidenceIn], list[ResidenceIn]]:
    """Route items by whether the scraper supplied a `bag_id`. Legacy scrapers
    do; the post-PR-4 scraper won't, and those go through API-side BAG
    resolution. Empty-string `bag_id` is treated as absent."""
    legacy: list[ResidenceIn] = []
    pending: list[ResidenceIn] = []
    for item in items:
        (legacy if item.bag_id else pending).append(item)
    return legacy, pending


def _dedup_by_bag_id(items: list[ResidenceIn]) -> list[ResidenceIn]:
    """Keep the first occurrence of each bag_id within a single payload.
    A single scrape can surface the same property twice (duplicate cards on a
    results page); collapse on bag_id so we don't fight ourselves on the upsert.
    """
    seen: dict[str, ResidenceIn] = {}
    for item in items:
        if item.bag_id:
            seen.setdefault(item.bag_id, item)
    return list(seen.values())


def _ingest_residences(items: list[ResidenceIn], *, scraped_at: datetime) -> tuple[int, int]:
    """Upsert residences, returning (new_residences_count, new_listings_count).

    The "existing" snapshot is taken before any writes so newly-created rows
    aren't counted as pre-existing.
    """
    payload_bag_ids = {item.bag_id for item in items if item.bag_id}
    payload_urls = {item.detail_url for item in items}
    existing_bag_ids = set(Residence.objects.filter(bag_id__in=payload_bag_ids).values_list("bag_id", flat=True))
    existing_urls = set(Listing.objects.filter(url__in=payload_urls).values_list("url", flat=True))

    for item in items:
        _upsert_residence(item, scraped_at=scraped_at)

    return len(payload_bag_ids - existing_bag_ids), len(payload_urls - existing_urls)


def _ingest_pending_listings(items: list[ResidenceIn], *, scraped_at: datetime) -> int:
    """Upsert listings without bag_id, marking them PENDING and queuing
    `scraping.resolve_bag` for each. Returns count of newly-created listings.
    Tasks are dispatched on transaction commit so a rollback doesn't leave
    orphan jobs running against rows that no longer exist."""
    if not items:
        return 0

    payload_urls = {item.detail_url for item in items}
    existing_urls = set(Listing.objects.filter(url__in=payload_urls).values_list("url", flat=True))

    for item in items:
        listing = _upsert_pending_listing(item, scraped_at=scraped_at)
        if listing.bag_status == BagStatus.PENDING:
            transaction.on_commit(lambda pk=listing.pk: resolve_bag.delay(pk))

    return len(payload_urls - existing_urls)


def _upsert_pending_listing(item: ResidenceIn, *, scraped_at: datetime) -> Listing:
    defaults = _listing_defaults_pending(item, scraped_at=scraped_at)
    listing, created = Listing.objects.get_or_create(url=item.detail_url, defaults=defaults)
    if not created:
        # Refresh per-portal scraped fields but don't touch FK / BAG state —
        # a previously-resolved listing must keep its residence link, and a
        # listing that already failed terminally shouldn't bounce back to PENDING.
        for field, value in defaults.items():
            if field in {"residence", "bag_status", "bag_resolved_at", "bag_failure_reason"}:
                continue
            setattr(listing, field, value)
        listing.save()
    return listing


def _listing_defaults_pending(item: ResidenceIn, *, scraped_at: datetime) -> dict:
    return {
        "residence": None,
        "website": item.website,
        "title": item.title,
        "price": item.price,
        "price_eur": _parse_price_eur(item.price),
        "image_url": item.image_url,
        "status": item.status,
        "scraped_at": scraped_at,
        "last_seen_at": scraped_at,
        "street": item.street,
        "house_number": item.house_number,
        "house_letter": item.house_letter,
        "house_number_suffix": item.house_number_suffix,
        "postcode": item.postcode,
        "city": item.city,
        "bag_status": BagStatus.PENDING,
    }


def _upsert_residence(item: ResidenceIn, *, scraped_at: datetime) -> Residence:
    residence, created = Residence.objects.get_or_create(
        bag_id=item.bag_id,
        defaults=_residence_defaults(item, scraped_at=scraped_at),
    )
    if not created:
        _apply_residence_update(residence, item, scraped_at=scraped_at)

    # If the URL is already attached to a different Residence (e.g. a parser
    # fix changed the BAG match across runs), keep the existing FK. Re-wiring
    # listings between residences is intentionally a manual /admin operation,
    # not the auto-ingest path.
    listing_defaults = _listing_defaults(item, residence=residence, scraped_at=scraped_at)
    listing, created = Listing.objects.get_or_create(url=item.detail_url, defaults=listing_defaults)
    if not created:
        for field, value in listing_defaults.items():
            if field == "residence":
                continue
            setattr(listing, field, value)
        listing.save()
    if listing.residence_id == residence.pk:
        reconcile_residence(residence)
    return residence


def _listing_defaults(item: ResidenceIn, *, residence: Residence, scraped_at: datetime) -> dict:
    return {
        "residence": residence,
        "website": item.website,
        "title": item.title,
        "price": item.price,
        "price_eur": _parse_price_eur(item.price),
        "image_url": item.image_url,
        "status": item.status,
        "scraped_at": scraped_at,
        "last_seen_at": scraped_at,
        "street": item.street,
        "house_number": item.house_number,
        "house_letter": item.house_letter,
        "house_number_suffix": item.house_number_suffix,
        "postcode": item.postcode,
        "city": item.city,
        "bag_status": BagStatus.RESOLVED,
        "bag_resolved_at": scraped_at,
    }


def _residence_defaults(item: ResidenceIn, *, scraped_at: datetime) -> dict:
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
        "status_changed_at": timezone.now(),
        "scraped_at": scraped_at,
    }


# TODO: figure out a more elegant way of doing this
def _apply_residence_update(residence: Residence, item: ResidenceIn, *, scraped_at: datetime) -> None:
    # Always-update fields: capture price drops, status transitions, and freshness.
    residence.price = item.price
    residence.price_eur = _parse_price_eur(item.price)
    if residence.status != item.status:
        residence.status = item.status
        residence.status_changed_at = timezone.now()
    residence.scraped_at = scraped_at
    # Complement-only fields: fill columns currently NULL but never
    # overwrite a value that's already present (including 0 / "").
    for field in _COMPLEMENT_FIELDS:
        if getattr(residence, field) is None and (incoming := getattr(item, field)) is not None:
            setattr(residence, field, incoming)
    residence.save()


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
