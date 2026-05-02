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
    duration = (payload.finished_at - payload.started_at).total_seconds()
    detail_urls = [listing.detail_url for listing in payload.listings]
    existing_count_before = Listing.objects.filter(detail_url__in=detail_urls).count()

    candidates = [
        Listing(
            website=listing.website,
            detail_url=listing.detail_url,
            title=listing.title,
            price=listing.price,
            price_eur=_parse_price_eur(listing.price),
            city=listing.city,
            street=listing.street,
            house_number=listing.house_number,
            house_number_suffix=listing.house_number_suffix,
            postcode=listing.postcode,
            bag_id=listing.bag_id,
            property_type=listing.property_type,
            bedrooms=listing.bedrooms,
            area_sqm=listing.area_sqm,
            image_url=listing.image_url,
            scraped_at=datetime.now(UTC),
        )
        for listing in payload.listings
    ]

    run_status = ScrapeRunStatus.FAILED if payload.error_message else ScrapeRunStatus.SUCCESS

    with transaction.atomic():
        if candidates:
            Listing.objects.bulk_create(candidates, ignore_conflicts=True)
        existing_count_after = Listing.objects.filter(detail_url__in=detail_urls).count()
        listings_new = existing_count_after - existing_count_before
        scrape_run = ScrapeRun.objects.create(
            website=website,
            started_at=payload.started_at,
            finished_at=payload.finished_at,
            status=run_status,
            listings_found=len(payload.listings),
            listings_new=listings_new,
            error_message=payload.error_message,
            duration_seconds=duration,
        )

    logger.info(f"Scrape run for {website}: {listings_new} new / {len(payload.listings)} found in {duration:.1f}s")
    return scrape_run


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
