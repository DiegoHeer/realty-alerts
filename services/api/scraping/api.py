import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.db import OperationalError, connection, transaction
from loguru import logger
from ninja import NinjaAPI, Router, Schema
from ninja.responses import Status
from ninja.security import APIKeyHeader

from scraping.models import BagStatus, Listing, ScrapeRun, ScrapeRunStatus, Website
from scraping.schemas import ListingIn, ScrapeResultsIn, ScrapeRunOut
from scraping.tasks import resolve_bag


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
    now = datetime.now(UTC)
    duration = (payload.finished_at - payload.started_at).total_seconds()
    run_status = ScrapeRunStatus.FAILED if payload.error_message else ScrapeRunStatus.SUCCESS

    with transaction.atomic():
        new_listings_count = _ingest_listings(payload.listings, scraped_at=now)

        scrape_run = ScrapeRun.objects.create(
            website=website,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            status=run_status,
            listings_found=len(payload.listings),
            new_listings_count=new_listings_count,
            error_message=payload.error_message,
            duration_seconds=duration,
        )

    logger.info(
        f"Scrape run for {website}: {new_listings_count} new listings / "
        f"{len(payload.listings)} found in {duration:.1f}s"
    )
    return scrape_run


def _ingest_listings(items: list[ListingIn], *, scraped_at: datetime) -> int:
    """Upsert one Listing per detail_url with the freshest per-portal scrape
    data. New listings get `bag_status='pending'` and a `scraping.resolve_bag`
    task queued via `transaction.on_commit` — a rolled-back ingest must not
    leave orphan jobs running against rows that never committed."""
    if not items:
        return 0

    payload_urls = {item.detail_url for item in items}
    existing_urls = set(Listing.objects.filter(url__in=payload_urls).values_list("url", flat=True))

    for item in items:
        listing = _upsert_listing(item, scraped_at=scraped_at)
        if listing.bag_status == BagStatus.PENDING:
            transaction.on_commit(lambda pk=listing.pk: resolve_bag.delay(pk))

    return len(payload_urls - existing_urls)


def _upsert_listing(item: ListingIn, *, scraped_at: datetime) -> Listing:
    defaults = _listing_defaults(item, scraped_at=scraped_at)
    listing, created = Listing.objects.get_or_create(url=item.detail_url, defaults=defaults)
    if not created:
        # Refresh per-portal scraped fields but preserve `residence` /
        # `bag_status` / `bag_resolved_at` / `bag_failure_reason` — a
        # previously-resolved listing must keep its FK link, and a listing
        # that already failed terminally shouldn't bounce back to PENDING.
        for field, value in defaults.items():
            if field in {"residence", "bag_status", "bag_resolved_at", "bag_failure_reason"}:
                continue
            setattr(listing, field, value)
        listing.save()
    return listing


def _listing_defaults(item: ListingIn, *, scraped_at: datetime) -> dict:
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
