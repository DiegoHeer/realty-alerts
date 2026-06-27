import hmac
from datetime import UTC, datetime
from typing import Annotated

from django.conf import settings
from django.db import OperationalError, connection, transaction
from loguru import logger
from ninja import NinjaAPI, Query, Router, Schema
from ninja.responses import Status
from ninja.security import APIKeyHeader

from scraping.models import (
    BagStatus,
    City,
    DetailScrapeRun,
    DetailScrapeRunStatus,
    District,
    ListScrapeRun,
    ListScrapeRunStatus,
    Listing,
    Neighborhood,
    Residence,
    Website,
)
from scraping.schemas import (
    CityOut,
    CityStatsOut,
    DetailListingIn,
    DetailResultIn,
    DetailResultStatus,
    DetailScrapeRunOut,
    DistrictStatsOut,
    GeoCityOut,
    GeoDistrictOut,
    GeoNeighborhoodOut,
    ListingIn,
    ListScrapeRunOut,
    NeighborhoodStatsOut,
    ResidenceFilters,
    ResidencePage,
    ResidenceOut,
    ScrapeResultsIn,
)
from scraping.reconciliation import reconcile_residence
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


v1_router = Router()


def _resolve_api_version(request, api_version: int | None) -> int:
    """Resolve the response-contract version: explicit query param wins, then
    the `X-API-Version` header, else legacy 1. A non-integer header is ignored."""
    if api_version is not None:
        return api_version
    header = request.headers.get("X-API-Version")
    if header is not None:
        try:
            return int(header)
        except ValueError:
            return 1
    return 1


@v1_router.get("/residences", response=list[ResidenceOut] | ResidencePage, tags=["catalog"])
def list_residences(
    request,
    filters: Query[ResidenceFilters],
    api_version: int | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,  # ty: ignore[call-non-callable]
    offset: Annotated[int, Query(ge=0)] = 0,  # ty: ignore[call-non-callable]
):
    qs = Residence.objects.prefetch_related("listings").order_by("-created_at")

    if filters.city:
        qs = qs.filter(city__icontains=filters.city)
    if filters.neighbourhood:
        qs = qs.filter(neighbourhood__icontains=filters.neighbourhood)
    if filters.district:
        qs = qs.filter(district__icontains=filters.district)
    if filters.street:
        qs = qs.filter(street__icontains=filters.street)
    if filters.postcode:
        qs = qs.filter(postcode__iexact=filters.postcode)
    if filters.min_price is not None:
        qs = qs.filter(current_price_eur__gte=filters.min_price)
    if filters.max_price is not None:
        qs = qs.filter(current_price_eur__lte=filters.max_price)
    if filters.status:
        qs = qs.filter(current_status=filters.status)

    if _resolve_api_version(request, api_version) >= 2:
        total = qs.count()
        items = list(qs[offset : offset + limit])
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + len(items) < total,
        }

    return list(qs[offset : offset + limit])


internal_router = Router()


@internal_router.get("/scrape-runs/{website}/last-successful", response=ListScrapeRunOut | None)
def get_last_successful_run(request, website: Website):
    return (
        ListScrapeRun.objects.filter(website=website, status=ListScrapeRunStatus.SUCCESS)
        .order_by("-started_at")
        .first()
    )


@internal_router.get("/scrape-runs/active", response=list[ListScrapeRunOut])
def get_active_runs(request):
    return list(ListScrapeRun.objects.filter(status=ListScrapeRunStatus.RUNNING))


@internal_router.post("/scrape-runs/{website}/results", response=ListScrapeRunOut)
def submit_scrape_results(request, website: Website, payload: ScrapeResultsIn):
    now = datetime.now(UTC)
    duration = (payload.finished_at - payload.started_at).total_seconds()
    run_status = ListScrapeRunStatus.FAILED if payload.error_message else ListScrapeRunStatus.SUCCESS

    with transaction.atomic():
        new_listings_count = _ingest_listings(payload.listings, scraped_at=now)

        scrape_run = ListScrapeRun.objects.create(
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
        "list_scraped_at": scraped_at,
        "last_seen_at": scraped_at,
        "street": item.street,
        "house_number": item.house_number,
        "house_letter": item.house_letter,
        "house_number_suffix": item.house_number_suffix,
        "postcode": item.postcode,
        "city": item.city,
        "bag_status": BagStatus.PENDING,
    }


_DETAIL_OPTIONAL_FIELDS = (
    "surface_area_m2",
    "bedroom_count",
    "bathroom_count",
    "room_count",
    "construction_period",
    "energy_label",
    "building_type",
    "construction_type",
)


def _apply_detail_to_listing(listing: Listing, detail: DetailListingIn, finished_at: datetime) -> None:
    listing.price = detail.price
    listing.status = detail.status
    listing.detail_scraped_at = finished_at
    update_fields = ["price", "status", "detail_scraped_at"]

    for field in _DETAIL_OPTIONAL_FIELDS:
        if (value := getattr(detail, field)) is not None:
            setattr(listing, field, value)
            update_fields.append(field)

    if detail.postcode:
        if listing.postcode and listing.postcode != detail.postcode:
            logger.warning(
                f"Postcode mismatch for listing_id={listing.pk}: existing={listing.postcode}, scraped={detail.postcode}"
            )
        elif not listing.postcode:
            listing.postcode = detail.postcode
            update_fields.append("postcode")

    listing.save(update_fields=update_fields)

    if listing.residence:
        reconcile_residence(listing.residence)


def _mark_run_success(run: DetailScrapeRun, finished_at: datetime, duration: float) -> None:
    run.status = DetailScrapeRunStatus.SUCCESS
    run.finished_at = finished_at
    run.duration_seconds = duration
    run.save(update_fields=["status", "finished_at", "duration_seconds"])


def _mark_run_failed(run: DetailScrapeRun, finished_at: datetime, duration: float, error_message: str | None) -> None:
    run.status = DetailScrapeRunStatus.FAILED
    run.error_message = error_message
    run.finished_at = finished_at
    run.duration_seconds = duration
    run.save(update_fields=["status", "error_message", "finished_at", "duration_seconds"])


@internal_router.patch("/listings/{listing_id}/detail", response={200: DetailScrapeRunOut, 404: None})
def submit_detail_result(request, listing_id: int, payload: DetailResultIn):
    listing = Listing.objects.filter(pk=listing_id).first()
    if listing is None:
        logger.warning(f"Detail result for unknown listing_id={listing_id}")
        return Status(404, None)

    run = (
        DetailScrapeRun.objects.filter(
            listing_id=listing_id,
            status=DetailScrapeRunStatus.DISPATCHED,
        )
        .order_by("-dispatched_at")
        .first()
    )
    if run is None:
        logger.warning(f"No DISPATCHED DetailScrapeRun for listing_id={listing_id}")
        return Status(404, None)

    duration = (payload.finished_at - payload.started_at).total_seconds()

    if payload.status == DetailResultStatus.SUCCESS and payload.detail:
        _apply_detail_to_listing(listing, payload.detail, payload.finished_at)
        _mark_run_success(run, payload.finished_at, duration)
        logger.info(f"Detail scrape succeeded for listing_id={listing_id} in {duration:.1f}s")
    else:
        _mark_run_failed(run, payload.finished_at, duration, payload.error_message)
        logger.warning(f"Detail scrape failed for listing_id={listing_id} in {duration:.1f}s: {payload.error_message}")

    return run


@v1_router.get("/cities", response=list[CityOut], tags=["catalog"])
def list_cities(request):
    return list(City.objects.all().order_by("name"))


@v1_router.get("/stats/cities/{city_id}", response={200: CityStatsOut, 404: None}, tags=["stats"])
def get_city_stats(request, city_id: str):
    city = City.objects.filter(code=city_id).first()
    if city is None:
        return Status(404, None)
    return city


class _CityRequired(Schema):
    city: str


@v1_router.get("/stats/districts", response={200: list[DistrictStatsOut], 404: None}, tags=["stats"])
def list_district_stats(request, filters: Query[_CityRequired], include: str | None = None):
    city = City.objects.filter(code=filters.city).first()
    if city is None:
        return Status(404, None)
    qs = District.objects.filter(city=city).select_related("city").order_by("name")
    districts = list(qs)
    if include != "geometry":
        for d in districts:
            d.geometry = None
    return districts


@v1_router.get("/stats/neighborhoods", response={200: list[NeighborhoodStatsOut], 404: None}, tags=["stats"])
def list_neighborhood_stats(request, filters: Query[_CityRequired], include: str | None = None):
    city = City.objects.filter(code=filters.city).first()
    if city is None:
        return Status(404, None)
    qs = Neighborhood.objects.filter(city=city).select_related("city", "district").order_by("name")
    neighborhoods = list(qs)
    if include != "geometry":
        for n in neighborhoods:
            n.geometry = None
    return neighborhoods


class _OptionalCity(Schema):
    city: str | None = None


@v1_router.get("/shapes/cities", response=list[GeoCityOut], tags=["shapes"])
def list_city_shapes(request):
    return list(City.objects.filter(geometry__isnull=False).order_by("name"))


@v1_router.get("/shapes/districts", response={200: list[GeoDistrictOut], 404: None}, tags=["shapes"])
def list_district_shapes(request, filters: Query[_OptionalCity]):
    if filters.city:
        city = City.objects.filter(code=filters.city).first()
        if city is None:
            return Status(404, None)
        return list(District.objects.filter(city=city, geometry__isnull=False).select_related("city").order_by("name"))
    return list(District.objects.filter(geometry__isnull=False).select_related("city").order_by("name"))


@v1_router.get("/shapes/neighborhoods", response={200: list[GeoNeighborhoodOut], 404: None}, tags=["shapes"])
def list_neighborhood_shapes(request, filters: Query[_OptionalCity]):
    if filters.city:
        city = City.objects.filter(code=filters.city).first()
        if city is None:
            return Status(404, None)
        return list(
            Neighborhood.objects.filter(city=city, geometry__isnull=False)
            .select_related("city", "district")
            .order_by("name")
        )
    return list(Neighborhood.objects.filter(geometry__isnull=False).select_related("city", "district").order_by("name"))


api.add_router("/internal/v1", internal_router, auth=InternalApiKey())
api.add_router("/v1", v1_router)


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
