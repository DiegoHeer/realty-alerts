# Detail Scraper — Design Spec

**Date:** 2026-05-13
**Status:** Approved

## Overview

Add detail-page scraping to the existing scraper architecture. Where the current list scraper extracts one `Listing` per card from a search-results page, the detail scraper fetches the individual listing URL and extracts richer property attributes. It is triggered on demand from the Django admin panel via a "Detail scrape" action, rather than on a beat schedule.

All three portals (Funda, Pararius, VastgoedNL) are in scope. Scraped detail fields are stored on `Listing` (raw per-portal) and reconciled onto `Residence` (aggregated across portals).

---

## Architecture & Flow

The existing list-scrape path is unchanged. The detail-scrape path reuses the same Argo Events webhook with an extended payload (Option B — mode discriminator):

```
Admin selects Listings or Residences
  → "Detail scrape" action
    → detail_scrape.delay(listing_id)    [one Celery task per listing]
      → POST ARGO_EVENTS_WEBHOOK_URL     [same URL, extended payload]
        → Argo Events Sensor
          → K8s Job (same scraper image)
              WEBSITE=<website>
              SCRAPE_MODE=detail
              DETAIL_URL=<listing.url>
              LISTING_ID=<listing.id>
            → scraper._run_detail(settings)
            → scraper.scrape_detail(url) → DetailListing
            → PATCH /internal/v1/listings/{id}/detail
              → update Listing detail fields + scraped_at + detail_scraped_at
              → reconcile_residence(listing.residence)
                → push reconciled aggregates to Residence
```

The Argo Events Sensor's existing Job template needs one update: pass `SCRAPE_MODE`, `DETAIL_URL`, and `LISTING_ID` as env vars (empty string when absent; pydantic-settings treats empty string as `None` for optional fields).

---

## Data Model

### `Listing` — new columns (all nullable, no backfill required)

| Field | Django type |
|---|---|
| `surface_area_m2` | `PositiveIntegerField(null=True, blank=True)` |
| `bedroom_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `bathroom_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `room_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `construction_period` | `CharField(max_length=20, null=True, blank=True)` — e.g. `"1960-1970"`, `"voor 1945"` |
| `energy_label` | `CharField(max_length=10, null=True, blank=True)` — e.g. `"A+"`, `"B"` |
| `detail_scraped_at` | `DateTimeField(null=True, blank=True)` — timestamp of last successful detail scrape |

`energy_label` is stored as a plain string. Dutch energy labels (`A++++` through `G`) are normalised to a canonical form by each portal's `scrape_detail` implementation; no DB-level choices constraint is added.

### `Residence` — same six new columns (no `detail_scraped_at`)

| Field | Django type |
|---|---|
| `surface_area_m2` | `PositiveIntegerField(null=True, blank=True)` |
| `bedroom_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `bathroom_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `room_count` | `PositiveSmallIntegerField(null=True, blank=True)` |
| `construction_period` | `CharField(max_length=20, null=True, blank=True)` |
| `energy_label` | `CharField(max_length=10, null=True, blank=True)` |

### Reconciliation strategy for new fields

`reconcile_residence` is extended to pick each detail field's value from the resolved `Listing` with the most recent non-null `detail_scraped_at`. Physical characteristics don't meaningfully differ between portals; recency is the tiebreaker. If no resolved listing has been detail-scraped yet, the field stays `null` on `Residence`.

### Migration

Single migration — all columns are nullable, no phased rollout or data migration needed.

---

## Scraper Service Changes (`services/scraper/`)

### `enums.py`
Add `ScrapeMode` alongside existing enums:
```python
class ScrapeMode(StrEnum):
    LIST = "list"
    DETAIL = "detail"
```

### `settings.py`
Three new fields with a model validator:
```python
scrape_mode: ScrapeMode = ScrapeMode.LIST
detail_url: str | None = None
listing_id: int | None = None

@model_validator(mode="after")
def _validate_detail_mode(self) -> Self:
    if self.scrape_mode == ScrapeMode.DETAIL:
        if self.detail_url is None:
            raise ValueError("detail_url is required when scrape_mode is 'detail'")
        if self.listing_id is None:
            raise ValueError("listing_id is required when scrape_mode is 'detail'")
    return self
```

### `models.py`
New `DetailListing` Pydantic model alongside `Listing`:
```python
class DetailListing(BaseModel):
    price: str
    status: ListingStatus
    surface_area_m2: int | None = None
    bedroom_count: int | None = None
    bathroom_count: int | None = None
    room_count: int | None = None
    construction_period: str | None = None
    energy_label: str | None = None
```

### `protocols.py`
`Scraper` renamed to `ListScraper`, `scrape` renamed to `scrape_list`. New `DetailScraper` added:
```python
class ListScraper(Protocol):
    website: Website
    def scrape_list(self, since: datetime | None) -> list[Listing]: ...

class DetailScraper(Protocol):
    website: Website
    def scrape_detail(self, url: str) -> DetailListing: ...
```

### `scrapers/` (FundaScraper, ParariusScraper, VastgoedNLScraper)
- `scrape()` renamed to `scrape_list()` on all three classes
- Each gains `scrape_detail(self, url: str) -> DetailListing` with a private `_parse_detail_page` helper
- All three satisfy both `ListScraper` and `DetailScraper` structurally — no new base class needed

### `runner.py`
- `SCRAPER_MAP` renamed to `PORTAL_SCRAPER_MAP` (reused for both modes)
- `run()` branches at the top; existing list logic extracted to `_run_list()`, new `_run_detail()` added:
```python
def run() -> None:
    settings = Settings()
    if settings.scrape_mode == ScrapeMode.DETAIL:
        _run_detail(settings)
    else:
        _run_list(settings)
```

### `client.py`
New method added:
```python
def submit_detail_result(self, listing_id: int, detail: DetailListing) -> None:
    response = self.client.patch(
        f"/internal/v1/listings/{listing_id}/detail",
        json=detail.model_dump(),
    )
    response.raise_for_status()
```

---

## API Service Changes (`services/api/`)

### `schemas.py`
Extend `ScrapeDispatchPayload` (backward-compatible — existing callers omit new fields):
```python
class ScrapeDispatchPayload(Schema):
    website: Website
    run_id: str
    scrape_mode: str = "list"
    detail_url: str | None = None
    listing_id: int | None = None
```

New `DetailResultIn` schema:
```python
class DetailResultIn(Schema):
    price: str
    status: str
    surface_area_m2: int | None = None
    bedroom_count: int | None = None
    bathroom_count: int | None = None
    room_count: int | None = None
    construction_period: str | None = None
    energy_label: str | None = None
```

### `tasks.py`
New `detail_scrape` task — same retry/backoff profile as `dispatch_scrape`:
```python
@shared_task(name="scraping.detail_scrape",
             autoretry_for=(httpx.HTTPError,),
             retry_backoff=True, retry_backoff_max=60, max_retries=3)
def detail_scrape(listing_id: int) -> str:
    listing = Listing.objects.get(pk=listing_id)
    payload = ScrapeDispatchPayload(
        website=listing.website,
        run_id=uuid.uuid4().hex,
        scrape_mode="detail",
        detail_url=listing.url,
        listing_id=listing_id,
    )
    webhook_url = settings.ARGO_EVENTS_WEBHOOK_URL
    if not webhook_url:
        logger.warning("ARGO_EVENTS_WEBHOOK_URL not set; skipping detail scrape for listing {}", listing_id)
        return payload.run_id
    with httpx.Client(timeout=10.0) as client:
        client.post(webhook_url, json=payload.model_dump(mode="json")).raise_for_status()
    return payload.run_id
```

### `api.py`
New internal endpoint:
```python
@internal_router.patch("/listings/{listing_id}/detail", response={200: ListingDetailOut, 404: None})
# ListingDetailOut is a new ninja.Schema to be defined in schemas.py — expose at minimum
# the fields updated by this endpoint (detail fields + price + status + detail_scraped_at).
def ingest_detail_result(request, listing_id: int, payload: DetailResultIn):
    listing = get_object_or_404(Listing, pk=listing_id)
    now = timezone.now()
    for field in ("surface_area_m2", "bedroom_count", "bathroom_count",
                  "room_count", "construction_period", "energy_label"):
        setattr(listing, field, getattr(payload, field))
    listing.price = payload.price
    listing.price_eur = _parse_price_eur(payload.price)
    listing.status = payload.status
    listing.detail_scraped_at = now
    listing.scraped_at = now
    listing.save()
    if listing.residence:
        reconcile_residence(listing.residence)
    return listing
```

### `reconciliation.py`
`reconcile_residence` extended — after the existing price/status/last_scraped_at pass, add:
```python
DETAIL_FIELDS = ("surface_area_m2", "bedroom_count", "bathroom_count",
                 "room_count", "construction_period", "energy_label")

detail_source = (
    Listing.objects
    .filter(residence=residence, bag_status=BagStatus.RESOLVED,
            detail_scraped_at__isnull=False)
    .order_by("-detail_scraped_at")
    .first()
)
for field in DETAIL_FIELDS:
    new_val = getattr(detail_source, field) if detail_source else None
    if getattr(residence, field) != new_val:
        setattr(residence, field, new_val)
        update_fields.append(field)
```

### `admin.py`
Two new actions registered on their respective `ModelAdmin` classes:
```python
@admin.action(description="Detail scrape selected listings")
def detail_scrape_listings(modeladmin, request, queryset):
    count = 0
    for listing in queryset:
        detail_scrape.delay(listing.pk)
        count += 1
    modeladmin.message_user(request, f"Queued detail scrape for {count} listing(s).", messages.SUCCESS)

@admin.action(description="Detail scrape selected residences")
def detail_scrape_residences(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        for listing in residence.listings.filter(bag_status=BagStatus.RESOLVED):
            detail_scrape.delay(listing.pk)
            count += 1
    modeladmin.message_user(request, f"Queued detail scrape for {count} listing(s).", messages.SUCCESS)
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| `SCRAPE_MODE=detail` but `DETAIL_URL` or `LISTING_ID` missing | `model_validator` raises `ValueError` at Job startup — exits non-zero immediately |
| Bot-detection interstitial on detail page | `ScrapingException` raised in `scrape_detail` — `_run_detail` logs error, exits non-zero |
| Detail page found but a field absent from HTML | Parser returns `None` — submitted as-is, stored as `null`, never a hard failure |
| `listing_id` not found at `PATCH .../detail` | 404 returned — scraper logs and exits non-zero |
| `ARGO_EVENTS_WEBHOOK_URL` not set | `detail_scrape` task no-ops with a warning log (same as `dispatch_scrape`) |
| Argo Events webhook returns non-2xx | `httpx.HTTPError` → Celery auto-retries (max 3, exponential backoff up to 60 s) |
| `listing.residence` is `None` at ingestion time | Detail fields saved on `Listing`; `reconcile_residence` skipped — no crash |

---

## Testing

### Scraper service
- Each portal's `_parse_detail_page` — happy-path fixture + partial fixture (some fields absent)
- `Settings` model validator rejects missing `detail_url` / `listing_id` in detail mode
- `_run_detail` / `_run_list` branching in `runner.py`
- `BackendClient.submit_detail_result` with `respx` mock

### API service
- `PATCH /internal/v1/listings/{id}/detail` — updates all fields, calls reconcile, returns 404 for unknown id
- `detail_scrape` Celery task — fires webhook with correct extended payload; no-ops cleanly when URL unset
- Updated `reconcile_residence` — detail fields pulled from most-recent `detail_scraped_at` listing; no crash when no detail-scraped listing exists yet
- `detail_scrape_listings` admin action — correct number of tasks queued
- `detail_scrape_residences` admin action — only resolved listings dispatched
