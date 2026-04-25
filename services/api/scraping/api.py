import hmac
from datetime import UTC, datetime

from django.conf import settings
from django.db import OperationalError, connection, transaction
from loguru import logger
from ninja import NinjaAPI, Router, Schema
from ninja.responses import Status
from ninja.security import APIKeyHeader

from scraping.models import Listing, ScrapeRun, ScrapeRunStatus, Website
from scraping.schemas import ScrapeResultsIn, ScrapeRunOut


class HealthOut(Schema):
    status: str


class InternalApiKey(APIKeyHeader):
    param_name = "X-API-Key"

    def authenticate(self, request, key):
        if key and hmac.compare_digest(key, settings.INTERNAL_API_KEY):
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
    duration = (payload.finished_at - payload.started_at).total_seconds()
    detail_urls = [listing.detail_url for listing in payload.listings]
    existing_urls = set(Listing.objects.filter(detail_url__in=detail_urls).values_list("detail_url", flat=True))

    new_listings = [
        Listing(
            website=listing.website,
            detail_url=listing.detail_url,
            title=listing.title,
            price=listing.price,
            price_cents=_parse_price_cents(listing.price),
            city=listing.city,
            property_type=listing.property_type,
            bedrooms=listing.bedrooms,
            area_sqm=listing.area_sqm,
            image_url=listing.image_url,
            scraped_at=datetime.now(UTC),
        )
        for listing in payload.listings
        if listing.detail_url not in existing_urls
    ]

    run_status = ScrapeRunStatus.FAILED if payload.error_message else ScrapeRunStatus.SUCCESS

    with transaction.atomic():
        if new_listings:
            Listing.objects.bulk_create(new_listings)
        scrape_run = ScrapeRun.objects.create(
            website=website,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            status=run_status,
            listings_found=len(payload.listings),
            listings_new=len(new_listings),
            error_message=payload.error_message,
            duration_seconds=duration,
        )

    logger.info(f"Scrape run for {website}: {len(new_listings)} new / {len(payload.listings)} found in {duration:.1f}s")
    return scrape_run


api.add_router("/internal/v1", internal_router, auth=InternalApiKey())


def _parse_price_cents(price_str: str) -> int | None:
    """Extract numeric value from Dutch price strings like '€ 350.000 k.k.' or '€ 1.250'."""
    cleaned = price_str.replace("€", "").replace("k.k.", "").replace("v.o.n.", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None
