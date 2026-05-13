# Detail Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add on-demand detail-page scraping for all three portals, triggered from the Django admin, enriching `Listing` and `Residence` records with price, status, and six new property attributes.

**Architecture:** Existing Argo Events webhook payload is extended with a mode discriminator (`scrape_mode=detail`, `detail_url`, `listing_id`); the same scraper container branches on `SCRAPE_MODE`. API service is implemented first (data model → schemas → reconciliation → endpoint → task → admin), then the scraper service (foundation → settings → runner → per-portal `scrape_detail`). Each scraper portal needs real HTML fixture files captured from live pages.

**Tech Stack:** Django 6, Django Ninja, Celery/Redis, Pydantic v2, BeautifulSoup4, Playwright (remote browser for Funda/Pararius), httpx (VastgoedNL), pytest, pytest-django, factory-boy, respx.

---

## File Map

### API service (`services/api/`)

| Action | Path |
|---|---|
| Modify | `scraping/models.py` |
| Auto-generate | `scraping/migrations/XXXX_add_listing_residence_detail_fields.py` |
| Modify | `scraping/schemas.py` |
| Modify | `scraping/reconciliation.py` |
| Modify | `scraping/api.py` |
| Modify | `scraping/tasks.py` |
| Modify | `scraping/admin.py` |
| Modify | `tests/factories.py` |
| Create | `tests/test_detail_scrape.py` |

### Scraper service (`services/scraper/`)

| Action | Path |
|---|---|
| Modify | `src/scraper/enums.py` |
| Modify | `src/scraper/settings.py` |
| Modify | `src/scraper/models.py` |
| Modify | `src/scraper/protocols.py` |
| Modify | `src/scraper/client.py` |
| Modify | `src/scraper/runner.py` |
| Modify | `src/scraper/scrapers/funda.py` |
| Modify | `src/scraper/scrapers/pararius.py` |
| Modify | `src/scraper/scrapers/vastgoed_nl.py` |
| Modify | `tests/conftest.py` |
| Create | `tests/data/funda_detail.html` |
| Create | `tests/data/pararius_detail.html` |
| Create | `tests/data/vastgoed_nl_detail.html` |
| Modify | `tests/scrapers/test_funda.py` |
| Modify | `tests/scrapers/test_pararius.py` |
| Modify | `tests/scrapers/test_vastgoed_nl.py` |

---

## Task 1 — API: Add detail fields to `Listing` and `Residence` models

**Files:**
- Modify: `services/api/scraping/models.py`
- Modify: `services/api/tests/factories.py`
- Create: `services/api/tests/test_detail_scrape.py`
- Auto-generate: `services/api/scraping/migrations/XXXX_add_listing_residence_detail_fields.py`

- [ ] **Step 1: Write failing tests**

Create `services/api/tests/test_detail_scrape.py`:

```python
from datetime import UTC, datetime
from typing import cast

import pytest

from scraping.models import BagStatus, Listing, Residence
from tests.factories import ListingFactory, ResidenceFactory

pytestmark = pytest.mark.django_db


def test_listing_accepts_detail_fields():
    from django.utils import timezone

    listing = ListingFactory(
        surface_area_m2=82,
        bedroom_count=3,
        bathroom_count=1,
        room_count=5,
        construction_period="1970-1980",
        energy_label="C",
        detail_scraped_at=timezone.now(),
    )
    listing.refresh_from_db()

    assert listing.surface_area_m2 == 82
    assert listing.bedroom_count == 3
    assert listing.bathroom_count == 1
    assert listing.room_count == 5
    assert listing.construction_period == "1970-1980"
    assert listing.energy_label == "C"
    assert listing.detail_scraped_at is not None


def test_listing_detail_fields_default_to_null():
    listing = ListingFactory()
    listing.refresh_from_db()

    assert listing.surface_area_m2 is None
    assert listing.bedroom_count is None
    assert listing.bathroom_count is None
    assert listing.room_count is None
    assert listing.construction_period is None
    assert listing.energy_label is None
    assert listing.detail_scraped_at is None


def test_residence_accepts_detail_fields():
    residence = ResidenceFactory(
        surface_area_m2=82,
        bedroom_count=3,
        bathroom_count=1,
        room_count=5,
        construction_period="1970-1980",
        energy_label="C",
    )
    residence.refresh_from_db()

    assert residence.surface_area_m2 == 82
    assert residence.bedroom_count == 3
    assert residence.bathroom_count == 1
    assert residence.room_count == 5
    assert residence.construction_period == "1970-1980"
    assert residence.energy_label == "C"


def test_residence_detail_fields_default_to_null():
    residence = ResidenceFactory()
    residence.refresh_from_db()

    assert residence.surface_area_m2 is None
    assert residence.bedroom_count is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_listing_accepts_detail_fields -v
```

Expected: `FAILED` — `TypeError: ListingFactory() got an unexpected keyword argument 'surface_area_m2'` (fields don't exist yet).

- [ ] **Step 3: Add fields to `Listing` in `scraping/models.py`**

After the `bag_failure_reason` field, add:

```python
    # Detail-page scraped fields — populated by detail scraper, null until first detail scrape
    surface_area_m2 = models.PositiveIntegerField(null=True, blank=True)
    bedroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    bathroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    room_count = models.PositiveSmallIntegerField(null=True, blank=True)
    construction_period = models.CharField(max_length=20, null=True, blank=True)
    energy_label = models.CharField(max_length=10, null=True, blank=True)
    detail_scraped_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: Add fields to `Residence` in `scraping/models.py`**

After the `status_changed_at` field, add:

```python
    # Reconciled detail attributes — sourced from the most recently detail-scraped resolved Listing
    surface_area_m2 = models.PositiveIntegerField(null=True, blank=True)
    bedroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    bathroom_count = models.PositiveSmallIntegerField(null=True, blank=True)
    room_count = models.PositiveSmallIntegerField(null=True, blank=True)
    construction_period = models.CharField(max_length=20, null=True, blank=True)
    energy_label = models.CharField(max_length=10, null=True, blank=True)
```

- [ ] **Step 5: Generate and inspect the migration**

```bash
cd services/api && uv run python manage.py makemigrations scraping --name add_listing_residence_detail_fields
```

Open the generated file and verify it adds all 13 new columns (7 on `listings`, 6 on `residences`), all nullable. No data migration needed.

- [ ] **Step 6: Apply migration**

```bash
cd services/api && uv run python manage.py migrate
```

- [ ] **Step 7: Run the new tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -v
```

Expected: all 4 new tests `PASS`.

- [ ] **Step 8: Verify existing tests still pass**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all existing tests pass (all new columns are nullable, no defaults changed).

- [ ] **Step 9: Commit**

```bash
git add scraping/models.py scraping/migrations/ tests/test_detail_scrape.py
git commit -m "feat(api): add detail fields to Listing and Residence models"
```

---

## Task 2 — API: Schemas (`DetailResultIn`, `ListingDetailOut`, extend `ScrapeDispatchPayload`)

**Files:**
- Modify: `services/api/scraping/schemas.py`
- Modify: `services/api/tests/test_detail_scrape.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_detail_scrape.py`:

```python
def test_detail_result_in_accepts_all_fields():
    from scraping.schemas import DetailResultIn

    schema = DetailResultIn(
        price="€ 425.000 k.k.",
        status="new",
        surface_area_m2=82,
        bedroom_count=3,
        bathroom_count=1,
        room_count=5,
        construction_period="1970-1980",
        energy_label="C",
    )

    assert schema.price == "€ 425.000 k.k."
    assert schema.surface_area_m2 == 82
    assert schema.energy_label == "C"


def test_detail_result_in_allows_null_detail_fields():
    from scraping.schemas import DetailResultIn

    schema = DetailResultIn(price="€ 350.000 k.k.", status="new")

    assert schema.surface_area_m2 is None
    assert schema.bedroom_count is None


def test_scrape_dispatch_payload_accepts_detail_mode():
    from scraping.schemas import ScrapeDispatchPayload
    from scraping.models import Website

    payload = ScrapeDispatchPayload(
        website=Website.FUNDA,
        run_id="abc123",
        scrape_mode="detail",
        detail_url="https://www.funda.nl/detail/some-listing/",
        listing_id=42,
    )

    assert payload.scrape_mode == "detail"
    assert payload.detail_url == "https://www.funda.nl/detail/some-listing/"
    assert payload.listing_id == 42


def test_scrape_dispatch_payload_defaults_to_list_mode():
    from scraping.schemas import ScrapeDispatchPayload
    from scraping.models import Website

    payload = ScrapeDispatchPayload(website=Website.FUNDA, run_id="abc123")

    assert payload.scrape_mode == "list"
    assert payload.detail_url is None
    assert payload.listing_id is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_detail_result_in_accepts_all_fields -v
```

Expected: `FAILED` — `ImportError: cannot import name 'DetailResultIn'`.

- [ ] **Step 3: Add schemas to `scraping/schemas.py`**

Add after `ScrapeResultsIn`:

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


class ListingDetailOut(Schema):
    id: int
    url: str
    website: Website
    price: str | None
    status: str
    surface_area_m2: int | None
    bedroom_count: int | None
    bathroom_count: int | None
    room_count: int | None
    construction_period: str | None
    energy_label: str | None
    detail_scraped_at: datetime | None
```

Extend `ScrapeDispatchPayload` (add three new fields at the end):

```python
class ScrapeDispatchPayload(Schema):
    """Body posted to the Argo Events webhook to spawn a scrape Job."""

    website: Website
    run_id: str
    scrape_mode: str = "list"
    detail_url: str | None = None
    listing_id: int | None = None
```

- [ ] **Step 4: Run schema tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -k "schema or dispatch_payload or detail_result" -v
```

Expected: 4 schema tests `PASS`.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scraping/schemas.py tests/test_detail_scrape.py
git commit -m "feat(api): add DetailResultIn, ListingDetailOut schemas; extend ScrapeDispatchPayload"
```

---

## Task 3 — API: Extend `reconcile_residence` for detail fields

**Files:**
- Modify: `services/api/scraping/reconciliation.py`
- Modify: `services/api/tests/test_detail_scrape.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_detail_scrape.py`:

```python
def test_reconcile_picks_detail_fields_from_most_recently_detail_scraped_listing():
    from scraping.reconciliation import reconcile_residence

    residence = cast(Residence, ResidenceFactory())
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        detail_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        surface_area_m2=75,
        bedroom_count=2,
        bathroom_count=1,
        room_count=3,
        construction_period="1960-1970",
        energy_label="D",
    )
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        detail_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        surface_area_m2=82,
        bedroom_count=3,
        bathroom_count=1,
        room_count=5,
        construction_period="1970-1980",
        energy_label="C",
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.surface_area_m2 == 82
    assert residence.bedroom_count == 3
    assert residence.bathroom_count == 1
    assert residence.room_count == 5
    assert residence.construction_period == "1970-1980"
    assert residence.energy_label == "C"


def test_reconcile_detail_fields_are_null_when_no_detail_scraped_listing():
    from scraping.reconciliation import reconcile_residence

    residence = cast(Residence, ResidenceFactory(bedroom_count=4))
    # Resolved listing exists but detail_scraped_at is null (never detail-scraped)
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        detail_scraped_at=None,
        bedroom_count=4,
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.bedroom_count is None


def test_reconcile_ignores_unresolved_listings_for_detail_fields():
    from scraping.reconciliation import reconcile_residence

    residence = cast(Residence, ResidenceFactory())
    # Only unresolved listing has been detail-scraped
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.PENDING,
        detail_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        bedroom_count=5,
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.bedroom_count is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_reconcile_picks_detail_fields_from_most_recently_detail_scraped_listing -v
```

Expected: `FAILED` — `AssertionError: assert None == 82` (detail fields not yet reconciled).

- [ ] **Step 3: Extend `reconcile_residence` in `scraping/reconciliation.py`**

Add `_DETAIL_FIELDS` as a module-level constant at the top of `reconciliation.py` (after the imports), then extend `reconcile_residence` with the new block after the existing `last_scraped_at` update:

```python
_DETAIL_FIELDS = (
    "surface_area_m2",
    "bedroom_count",
    "bathroom_count",
    "room_count",
    "construction_period",
    "energy_label",
)


def reconcile_residence(residence: Residence) -> None:
    """Recompute Residence's stored aggregates from its resolved Listings."""
    resolved = list(Listing.objects.filter(residence=residence, bag_status=BagStatus.RESOLVED))
    if not resolved:
        return

    # --- existing price / status / last_scraped_at logic (unchanged) ---
    prices = [listing.price_eur for listing in resolved if listing.price_eur is not None]
    new_price_eur = min(prices) if prices else None
    new_status = max((listing.status for listing in resolved), key=lambda s: _STATUS_ORDER[ListingStatus(s)])
    scraped_ats = [listing.scraped_at for listing in resolved if listing.scraped_at is not None]
    new_last_scraped_at = max(scraped_ats) if scraped_ats else None

    update_fields: list[str] = []
    if residence.current_price_eur != new_price_eur:
        residence.current_price_eur = new_price_eur
        update_fields.append("current_price_eur")
    if residence.current_status != new_status:
        residence.current_status = new_status
        residence.status_changed_at = timezone.now()
        update_fields.extend(("current_status", "status_changed_at"))
    if residence.last_scraped_at != new_last_scraped_at:
        residence.last_scraped_at = new_last_scraped_at
        update_fields.append("last_scraped_at")

    # --- new detail-field reconciliation ---
    detail_source = (
        Listing.objects.filter(
            residence=residence,
            bag_status=BagStatus.RESOLVED,
            detail_scraped_at__isnull=False,
        )
        .order_by("-detail_scraped_at")
        .first()
    )
    for field in _DETAIL_FIELDS:
        new_val = getattr(detail_source, field) if detail_source else None
        if getattr(residence, field) != new_val:
            setattr(residence, field, new_val)
            update_fields.append(field)

    if update_fields:
        residence.save(update_fields=update_fields)
```

- [ ] **Step 4: Run reconciliation tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -k "reconcile" -v
```

Expected: all 3 new reconciliation tests `PASS`.

- [ ] **Step 5: Run full suite**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all pass (existing reconciliation tests unchanged).

- [ ] **Step 6: Commit**

```bash
git add scraping/reconciliation.py tests/test_detail_scrape.py
git commit -m "feat(api): extend reconcile_residence to propagate detail fields to Residence"
```

---

## Task 4 — API: `PATCH /internal/v1/listings/{id}/detail` endpoint

**Files:**
- Modify: `services/api/scraping/api.py`
- Modify: `services/api/tests/test_detail_scrape.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_detail_scrape.py`:

```python
def test_ingest_detail_result_updates_listing_fields(client, api_key_headers):
    residence = cast(Residence, ResidenceFactory())
    listing = cast(
        Listing,
        ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED),
    )
    payload = {
        "price": "€ 425.000 k.k.",
        "status": "new",
        "surface_area_m2": 82,
        "bedroom_count": 3,
        "bathroom_count": 1,
        "room_count": 5,
        "construction_period": "1970-1980",
        "energy_label": "C",
    }

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 200
    listing.refresh_from_db()
    assert listing.surface_area_m2 == 82
    assert listing.bedroom_count == 3
    assert listing.bathroom_count == 1
    assert listing.room_count == 5
    assert listing.construction_period == "1970-1980"
    assert listing.energy_label == "C"
    assert listing.price == "€ 425.000 k.k."
    assert listing.detail_scraped_at is not None
    assert listing.scraped_at is not None


def test_ingest_detail_result_reconciles_residence(client, api_key_headers):
    residence = cast(Residence, ResidenceFactory(bedroom_count=None))
    listing = cast(
        Listing,
        ListingFactory(
            residence=residence,
            bag_status=BagStatus.RESOLVED,
            price_eur=500_000,
        ),
    )

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json={"price": "€ 450.000 k.k.", "status": "new", "bedroom_count": 4},
        headers=api_key_headers,
    )

    assert response.status_code == 200
    residence.refresh_from_db()
    assert residence.current_price_eur == 450_000
    assert residence.bedroom_count == 4


def test_ingest_detail_result_skips_reconcile_when_no_residence(client, api_key_headers):
    listing = cast(
        Listing,
        ListingFactory(residence=None, bag_status=BagStatus.PENDING),
    )

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json={"price": "€ 350.000 k.k.", "status": "new", "bedroom_count": 3},
        headers=api_key_headers,
    )

    assert response.status_code == 200
    listing.refresh_from_db()
    assert listing.bedroom_count == 3  # saved on listing


def test_ingest_detail_result_returns_404_for_unknown_listing(client, api_key_headers):
    response = client.patch(
        "/internal/v1/listings/99999/detail",
        json={"price": "€ 350.000 k.k.", "status": "new"},
        headers=api_key_headers,
    )
    assert response.status_code == 404


def test_ingest_detail_result_requires_api_key(client):
    response = client.patch(
        "/internal/v1/listings/1/detail",
        json={"price": "€ 350.000 k.k.", "status": "new"},
    )
    assert response.status_code == 401
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_ingest_detail_result_updates_listing_fields -v
```

Expected: `FAILED` — 404 (route not registered yet).

- [ ] **Step 3: Add the endpoint to `scraping/api.py`**

Add imports at top of file (if not already present):
```python
from django.shortcuts import get_object_or_404
from scraping.schemas import DetailResultIn, ListingDetailOut
```

Add the endpoint to `internal_router` (after the existing `submit_scrape_results`):

```python
@internal_router.patch("/listings/{listing_id}/detail", response={200: ListingDetailOut, 404: None})
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

    if listing.residence_id:
        reconcile_residence(listing.residence)

    return listing
```

Add import at top if not already present:
```python
from django.utils import timezone
from scraping.reconciliation import reconcile_residence
```

- [ ] **Step 4: Run endpoint tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -k "ingest_detail" -v
```

Expected: all 5 endpoint tests `PASS`.

- [ ] **Step 5: Run full suite**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scraping/api.py tests/test_detail_scrape.py
git commit -m "feat(api): add PATCH /internal/v1/listings/{id}/detail endpoint"
```

---

## Task 5 — API: `detail_scrape` Celery task

**Files:**
- Modify: `services/api/scraping/tasks.py`
- Modify: `services/api/tests/test_detail_scrape.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_detail_scrape.py`:

```python
import json
import httpx
import respx


@pytest.mark.django_db
@respx.mock
def test_detail_scrape_posts_extended_payload(settings):
    from scraping.tasks import detail_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    route = respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))
    listing = cast(Listing, ListingFactory(website="funda", url="https://www.funda.nl/detail/some-listing/"))

    run_id = detail_scrape.delay(listing.pk).get(timeout=1)

    assert run_id and len(run_id) == 32
    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["website"] == "funda"
    assert body["scrape_mode"] == "detail"
    assert body["detail_url"] == "https://www.funda.nl/detail/some-listing/"
    assert body["listing_id"] == listing.pk


@pytest.mark.django_db
def test_detail_scrape_short_circuits_when_url_unset(settings):
    from scraping.tasks import detail_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = None
    listing = cast(Listing, ListingFactory())

    # No respx mock — if an HTTP call were made, the test would error.
    run_id = detail_scrape.delay(listing.pk).get(timeout=1)

    assert run_id and len(run_id) == 32
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_detail_scrape_posts_extended_payload -v
```

Expected: `FAILED` — `ImportError: cannot import name 'detail_scrape'`.

- [ ] **Step 3: Add `detail_scrape` task to `scraping/tasks.py`**

```python
@shared_task(
    name="scraping.detail_scrape",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=60,
    max_retries=3,
)
def detail_scrape(listing_id: int) -> str:
    """POST a detail-scrape dispatch event to the Argo Events webhook.

    The same webhook URL as dispatch_scrape is reused; the extended payload
    carries scrape_mode='detail', detail_url, and listing_id so the Sensor's
    Job template can pass them as env vars to the scraper container."""
    listing = Listing.objects.get(pk=listing_id)
    payload = ScrapeDispatchPayload(
        website=Website(listing.website),
        run_id=uuid.uuid4().hex,
        scrape_mode="detail",
        detail_url=listing.url,
        listing_id=listing_id,
    )

    webhook_url = settings.ARGO_EVENTS_WEBHOOK_URL
    if not webhook_url:
        logger.warning(
            "ARGO_EVENTS_WEBHOOK_URL not set; skipping detail scrape for listing {}",
            listing_id,
        )
        return payload.run_id

    with httpx.Client(timeout=10.0) as client:
        response = client.post(webhook_url, json=payload.model_dump(mode="json"))
        response.raise_for_status()

    logger.info("Dispatched detail scrape for listing {} (run_id={})", listing_id, payload.run_id)
    return payload.run_id
```

Add `ScrapeDispatchPayload` to the imports at the top of `tasks.py`:
```python
from scraping.schemas import ScrapeDispatchPayload
```

- [ ] **Step 4: Run task tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -k "detail_scrape" -v
```

Expected: both task tests `PASS`.

- [ ] **Step 5: Run full suite**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scraping/tasks.py tests/test_detail_scrape.py
git commit -m "feat(api): add scraping.detail_scrape Celery task"
```

---

## Task 6 — API: Admin actions

**Files:**
- Modify: `services/api/scraping/admin.py`
- Modify: `services/api/tests/test_detail_scrape.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_detail_scrape.py`:

```python
from unittest.mock import MagicMock, patch
from django.contrib import messages


@pytest.mark.django_db
def test_detail_scrape_listings_queues_one_task_per_listing():
    from scraping.admin import detail_scrape_listings
    from scraping.models import Listing

    listings = [ListingFactory(), ListingFactory(), ListingFactory()]
    queryset = Listing.objects.filter(pk__in=[lst.pk for lst in listings])

    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.detail_scrape") as mock_task:
        detail_scrape_listings(modeladmin, request, queryset)

    assert mock_task.delay.call_count == 3
    dispatched_ids = {call.args[0] for call in mock_task.delay.call_args_list}
    assert dispatched_ids == {lst.pk for lst in listings}

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert len(success_calls) == 1
    assert "3" in success_calls[0].args[1]


@pytest.mark.django_db
def test_detail_scrape_residences_dispatches_only_resolved_listings():
    from scraping.admin import detail_scrape_residences
    from scraping.models import Residence

    residence = cast(Residence, ResidenceFactory())
    resolved = cast(Listing, ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED))
    ListingFactory(residence=residence, bag_status=BagStatus.BAG_NO_MATCH)
    ListingFactory(residence=residence, bag_status=BagStatus.PENDING)

    queryset = Residence.objects.filter(pk=residence.pk)
    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.detail_scrape") as mock_task:
        detail_scrape_residences(modeladmin, request, queryset)

    assert mock_task.delay.call_count == 1
    mock_task.delay.assert_called_once_with(resolved.pk)

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert len(success_calls) == 1
    assert "1" in success_calls[0].args[1]


@pytest.mark.django_db
def test_detail_scrape_residences_with_multiple_residences():
    from scraping.admin import detail_scrape_residences
    from scraping.models import Residence

    r1 = cast(Residence, ResidenceFactory())
    r2 = cast(Residence, ResidenceFactory())
    l1 = cast(Listing, ListingFactory(residence=r1, bag_status=BagStatus.RESOLVED))
    l2 = cast(Listing, ListingFactory(residence=r1, bag_status=BagStatus.RESOLVED))
    l3 = cast(Listing, ListingFactory(residence=r2, bag_status=BagStatus.RESOLVED))

    queryset = Residence.objects.filter(pk__in=[r1.pk, r2.pk])
    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.detail_scrape") as mock_task:
        detail_scrape_residences(modeladmin, request, queryset)

    assert mock_task.delay.call_count == 3
    dispatched_ids = {call.args[0] for call in mock_task.delay.call_args_list}
    assert dispatched_ids == {l1.pk, l2.pk, l3.pk}
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py::test_detail_scrape_listings_queues_one_task_per_listing -v
```

Expected: `FAILED` — `ImportError: cannot import name 'detail_scrape_listings'`.

- [ ] **Step 3: Add admin actions to `scraping/admin.py`**

Add import at top:
```python
from scraping.tasks import detail_scrape
```

Add the two action functions (before the `@admin.register` calls):

```python
@admin.action(description="Detail scrape selected listings")
def detail_scrape_listings(modeladmin, request, queryset):
    count = 0
    for listing in queryset:
        detail_scrape.delay(listing.pk)
        count += 1
    modeladmin.message_user(
        request,
        f"Queued detail scrape for {count} listing(s).",
        messages.SUCCESS,
    )


@admin.action(description="Detail scrape selected residences")
def detail_scrape_residences(modeladmin, request, queryset):
    count = 0
    for residence in queryset:
        for listing in residence.listings.filter(bag_status=BagStatus.RESOLVED):
            detail_scrape.delay(listing.pk)
            count += 1
    modeladmin.message_user(
        request,
        f"Queued detail scrape for {count} listing(s).",
        messages.SUCCESS,
    )
```

Register the actions on their respective `ModelAdmin` classes:

In `ListingAdmin`:
```python
actions = [promote_listings, detail_scrape_listings]
```

In `ResidenceAdmin`:
```python
actions = [detail_scrape_residences]
```

- [ ] **Step 4: Run admin action tests**

```bash
cd services/api && uv run pytest tests/test_detail_scrape.py -k "admin or residences or listings" -v
```

Expected: all 3 admin tests `PASS`.

- [ ] **Step 5: Run full suite**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Run pre-commit checks**

```bash
cd services/api && make pre-commit
```

Fix any lint/format errors before committing.

- [ ] **Step 7: Commit**

```bash
git add scraping/admin.py scraping/tasks.py tests/test_detail_scrape.py
git commit -m "feat(api): add detail_scrape_listings and detail_scrape_residences admin actions"
```

---

## Task 7 — Scraper: Foundation (ScrapeMode enum, DetailListing model, protocol rename)

**Files:**
- Modify: `services/scraper/src/scraper/enums.py`
- Modify: `services/scraper/src/scraper/models.py`
- Modify: `services/scraper/src/scraper/protocols.py`
- Modify: `services/scraper/src/scraper/scrapers/funda.py`
- Modify: `services/scraper/src/scraper/scrapers/pararius.py`
- Modify: `services/scraper/src/scraper/scrapers/vastgoed_nl.py`
- Modify: `services/scraper/src/scraper/runner.py`
- Modify: `services/scraper/tests/scrapers/test_funda.py`
- Modify: `services/scraper/tests/scrapers/test_pararius.py`
- Modify: `services/scraper/tests/scrapers/test_vastgoed_nl.py`

> **Note:** This task is a rename + addition. It touches many files but makes no behavioural change. All existing tests must remain green after each sub-step.

- [ ] **Step 1: Rename `scrape` → `scrape_list` on all three scraper classes**

In `services/scraper/src/scraper/scrapers/funda.py`, rename the method:
```python
def scrape_list(self, since: datetime | None) -> list[Listing]:   # was: scrape
```

In `services/scraper/src/scraper/scrapers/pararius.py`:
```python
def scrape_list(self, since: datetime | None) -> list[Listing]:   # was: scrape
```

In `services/scraper/src/scraper/scrapers/vastgoed_nl.py`:
```python
def scrape_list(self, since: datetime | None) -> list[Listing]:   # was: scrape
```

- [ ] **Step 2: Update `runner.py` to call `scrape_list`**

In `services/scraper/src/scraper/runner.py`, rename `SCRAPER_MAP` → `PORTAL_SCRAPER_MAP` and update the call:

```python
PORTAL_SCRAPER_MAP = {
    Website.FUNDA: FundaScraper,
    Website.PARARIUS: ParariusScraper,
    Website.VASTGOED_NL: VastgoedNLScraper,
}
```

In the run body (currently calls `scraper.scrape(since=since)`):
```python
scraper = PORTAL_SCRAPER_MAP[website](fetch=fetch)
listings = scraper.scrape_list(since=since)
```

- [ ] **Step 3: Update test files to use `scrape_list`**

In `tests/scrapers/test_funda.py`, every call to `funda_scraper.scrape(...)` becomes `funda_scraper.scrape_list(...)`.

In `tests/scrapers/test_pararius.py`, every call to `pararius_scraper.scrape(...)` becomes `pararius_scraper.scrape_list(...)`.

In `tests/scrapers/test_vastgoed_nl.py`, every call to `vastgoed_nl_scraper.scrape(...)` becomes `vastgoed_nl_scraper.scrape_list(...)`.

- [ ] **Step 4: Run existing scraper tests to confirm no regressions**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all existing tests `PASS`.

- [ ] **Step 5: Rename `Scraper` protocol → `ListScraper` in `protocols.py`; add `DetailScraper`**

Replace the entire content of `services/scraper/src/scraper/protocols.py`:

```python
from datetime import datetime
from typing import Protocol, Self

from scraper.enums import Website
from scraper.models import DetailListing, Listing


class FetchStrategy(Protocol):
    def fetch(self, url: str) -> str: ...
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc: object) -> None: ...


class ListScraper(Protocol):
    website: Website

    def scrape_list(self, since: datetime | None) -> list[Listing]: ...


class DetailScraper(Protocol):
    website: Website

    def scrape_detail(self, url: str) -> DetailListing: ...
```

- [ ] **Step 6: Add `ScrapeMode` to `enums.py`**

```python
class ScrapeMode(StrEnum):
    LIST = "list"
    DETAIL = "detail"
```

- [ ] **Step 7: Add `DetailListing` to `models.py`**

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

- [ ] **Step 8: Run full scraper test suite**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all existing tests still `PASS`.

- [ ] **Step 9: Commit**

```bash
git add src/scraper/enums.py src/scraper/models.py src/scraper/protocols.py \
        src/scraper/scrapers/funda.py src/scraper/scrapers/pararius.py \
        src/scraper/scrapers/vastgoed_nl.py src/scraper/runner.py \
        tests/scrapers/test_funda.py tests/scrapers/test_pararius.py \
        tests/scrapers/test_vastgoed_nl.py
git commit -m "refactor(scraper): rename Scraper→ListScraper, scrape→scrape_list; add DetailListing + DetailScraper"
```

---

## Task 8 — Scraper: Settings with `scrape_mode`, `detail_url`, `listing_id` + validator

**Files:**
- Modify: `services/scraper/src/scraper/settings.py`
- Create: `services/scraper/tests/test_settings.py`

- [ ] **Step 1: Write failing tests**

Create `services/scraper/tests/test_settings.py`:

```python
import pytest
from pydantic import ValidationError


def test_settings_defaults_to_list_mode(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "test-key")

    from scraper.settings import Settings

    s = Settings()
    from scraper.enums import ScrapeMode
    assert s.scrape_mode == ScrapeMode.LIST
    assert s.detail_url is None
    assert s.listing_id is None


def test_settings_detail_mode_valid_when_all_fields_provided(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "test-key")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("DETAIL_URL", "https://www.funda.nl/detail/some-listing/")
    monkeypatch.setenv("LISTING_ID", "42")

    from scraper.settings import Settings

    s = Settings()
    assert s.detail_url == "https://www.funda.nl/detail/some-listing/"
    assert s.listing_id == 42


def test_settings_detail_mode_rejects_missing_detail_url(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "test-key")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("LISTING_ID", "42")
    # DETAIL_URL intentionally absent

    from scraper.settings import Settings

    with pytest.raises(ValidationError, match="detail_url is required"):
        Settings()


def test_settings_detail_mode_rejects_missing_listing_id(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "test-key")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("DETAIL_URL", "https://www.funda.nl/detail/some-listing/")
    # LISTING_ID intentionally absent

    from scraper.settings import Settings

    with pytest.raises(ValidationError, match="listing_id is required"):
        Settings()
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/test_settings.py -v
```

Expected: `FAILED` — `ValidationError: 1 validation error for Settings` or `AttributeError` (fields don't exist yet).

- [ ] **Step 3: Extend `settings.py`**

```python
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from scraper.enums import ScrapeMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Job-specific
    website: str = Field(...)
    scrape_mode: ScrapeMode = ScrapeMode.LIST
    detail_url: str | None = None
    listing_id: int | None = None

    # Infrastructure
    backend_api_url: str = "http://localhost:8000"
    browser_url: str = "ws://localhost:3000"
    realty_api_key: str = Field(...)

    # Operational
    timezone: str = "Europe/Amsterdam"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _validate_detail_mode(self) -> Self:
        if self.scrape_mode == ScrapeMode.DETAIL:
            if self.detail_url is None:
                raise ValueError("detail_url is required when scrape_mode is 'detail'")
            if self.listing_id is None:
                raise ValueError("listing_id is required when scrape_mode is 'detail'")
        return self
```

- [ ] **Step 4: Run settings tests**

```bash
cd services/scraper && uv run pytest tests/test_settings.py -v
```

Expected: all 4 tests `PASS`.

- [ ] **Step 5: Run full suite**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/scraper/settings.py tests/test_settings.py
git commit -m "feat(scraper): add scrape_mode, detail_url, listing_id settings with model validator"
```

---

## Task 9 — Scraper: `BackendClient.submit_detail_result` + runner `_run_detail`/`_run_list` refactor

**Files:**
- Modify: `services/scraper/src/scraper/client.py`
- Modify: `services/scraper/src/scraper/runner.py`
- Create: `services/scraper/tests/test_client.py`
- Create: `services/scraper/tests/test_runner.py`

- [ ] **Step 1: Write failing tests for `BackendClient`**

Create `services/scraper/tests/test_client.py`:

```python
import httpx
import pytest
import respx

from scraper.client import BackendClient
from scraper.models import DetailListing
from scraper.enums import ListingStatus


@respx.mock
def test_submit_detail_result_patches_correct_endpoint():
    route = respx.patch("http://backend.test/internal/v1/listings/42/detail").mock(
        return_value=httpx.Response(200, json={})
    )
    client = BackendClient(base_url="http://backend.test", api_key="test-key")
    detail = DetailListing(
        price="€ 425.000 k.k.",
        status=ListingStatus.NEW,
        bedroom_count=3,
        surface_area_m2=82,
    )

    client.submit_detail_result(42, detail)

    assert route.called
    import json
    body = json.loads(route.calls.last.request.content)
    assert body["price"] == "€ 425.000 k.k."
    assert body["bedroom_count"] == 3
    assert body["surface_area_m2"] == 82


@respx.mock
def test_submit_detail_result_raises_on_non_2xx():
    respx.patch("http://backend.test/internal/v1/listings/99/detail").mock(
        return_value=httpx.Response(404)
    )
    client = BackendClient(base_url="http://backend.test", api_key="test-key")
    detail = DetailListing(price="€ 300.000 k.k.", status=ListingStatus.NEW)

    with pytest.raises(httpx.HTTPStatusError):
        client.submit_detail_result(99, detail)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/test_client.py -v
```

Expected: `FAILED` — `AttributeError: 'BackendClient' object has no attribute 'submit_detail_result'`.

- [ ] **Step 3: Add `submit_detail_result` to `client.py`**

```python
from scraper.models import DetailListing, Listing

def submit_detail_result(self, listing_id: int, detail: DetailListing) -> None:
    response = self.client.patch(
        f"/internal/v1/listings/{listing_id}/detail",
        json=detail.model_dump(),
    )
    response.raise_for_status()
```

- [ ] **Step 4: Run client tests**

```bash
cd services/scraper && uv run pytest tests/test_client.py -v
```

Expected: both tests `PASS`.

- [ ] **Step 5: Write failing runner tests**

Create `services/scraper/tests/test_runner.py`:

```python
from unittest.mock import MagicMock, patch

import pytest

import scraper.runner as runner_module
from scraper.enums import ScrapeMode


def _mock_settings(scrape_mode: ScrapeMode) -> MagicMock:
    s = MagicMock()
    s.scrape_mode = scrape_mode
    s.log_level = "INFO"
    s.website = "funda"
    return s


def test_run_branches_to_run_list_when_mode_is_list(monkeypatch):
    mock_run_list = MagicMock()
    mock_run_detail = MagicMock()
    monkeypatch.setattr(runner_module, "_run_list", mock_run_list)
    monkeypatch.setattr(runner_module, "_run_detail", mock_run_detail)

    settings = _mock_settings(ScrapeMode.LIST)
    with patch.object(runner_module, "Settings", return_value=settings):
        runner_module.run()

    mock_run_list.assert_called_once_with(settings)
    mock_run_detail.assert_not_called()


def test_run_branches_to_run_detail_when_mode_is_detail(monkeypatch):
    mock_run_list = MagicMock()
    mock_run_detail = MagicMock()
    monkeypatch.setattr(runner_module, "_run_list", mock_run_list)
    monkeypatch.setattr(runner_module, "_run_detail", mock_run_detail)

    settings = _mock_settings(ScrapeMode.DETAIL)
    with patch.object(runner_module, "Settings", return_value=settings):
        runner_module.run()

    mock_run_detail.assert_called_once_with(settings)
    mock_run_list.assert_not_called()
```

- [ ] **Step 6: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/test_runner.py -v
```

Expected: `FAILED` — `AttributeError: module 'scraper.runner' has no attribute '_run_list'`.

- [ ] **Step 7: Refactor `runner.py`**

Replace the current `run()` function with the refactored version (existing list-scrape logic moves into `_run_list`; new `_run_detail` added):

```python
import sys
from datetime import UTC, datetime

from loguru import logger

from scraper.client import BackendClient
from scraper.enums import ScrapeMode, Website
from scraper.fetch.http import HttpFetch
from scraper.fetch.playwright import PlaywrightFetch
from scraper.models import Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.funda import FundaScraper
from scraper.scrapers.pararius import ParariusScraper
from scraper.scrapers.vastgoed_nl import VastgoedNLScraper
from scraper.settings import Settings

PORTAL_SCRAPER_MAP = {
    Website.FUNDA: FundaScraper,
    Website.PARARIUS: ParariusScraper,
    Website.VASTGOED_NL: VastgoedNLScraper,
}


def run() -> None:
    settings = Settings()
    _configure_logging(settings.log_level)

    if settings.scrape_mode == ScrapeMode.DETAIL:
        _run_detail(settings)
    else:
        _run_list(settings)


def _run_list(settings: Settings) -> None:
    website = Website(settings.website)
    logger.info(f"Starting list scraper for {website}")

    client = BackendClient(base_url=settings.backend_api_url, api_key=settings.realty_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    since = client.get_last_successful_run(website)
    logger.info(f"Last successful run: {since or 'never'}")

    started_at = datetime.now(UTC)
    error_message: str | None = None
    listings: list[Listing] = []

    try:
        with _make_fetch(website, settings) as fetch:
            scraper = PORTAL_SCRAPER_MAP[website](fetch=fetch)
            listings = scraper.scrape_list(since=since)
            logger.info(f"Scraped {len(listings)} listings from {website}")
    except Exception as exc:
        error_message = str(exc)
        logger.exception(f"List scraping failed for {website}")

    finished_at = datetime.now(UTC)

    try:
        client.submit_results(
            website=website,
            listings=listings,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
        )
    except Exception as exc:
        logger.exception(f"Failed to submit results to backend API: {exc}")
        sys.exit(1)

    if error_message:
        sys.exit(1)

    logger.info(f"List scraper for {website} completed successfully")


def _run_detail(settings: Settings) -> None:
    website = Website(settings.website)
    logger.info(f"Starting detail scraper for {website}, url={settings.detail_url}")

    client = BackendClient(base_url=settings.backend_api_url, api_key=settings.realty_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    try:
        with _make_fetch(website, settings) as fetch:
            scraper = PORTAL_SCRAPER_MAP[website](fetch=fetch)
            detail = scraper.scrape_detail(settings.detail_url)
            logger.info(f"Detail scraped {settings.detail_url}")
    except Exception as exc:
        logger.exception(f"Detail scraping failed for {settings.detail_url}: {exc}")
        sys.exit(1)

    try:
        client.submit_detail_result(settings.listing_id, detail)
    except Exception as exc:
        logger.exception(f"Failed to submit detail result to backend API: {exc}")
        sys.exit(1)

    logger.info(f"Detail scraper for {website} completed successfully")


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)


def _make_fetch(website: Website, settings: Settings) -> FetchStrategy:
    if website in {Website.FUNDA, Website.PARARIUS}:
        return PlaywrightFetch(browser_url=settings.browser_url)
    return HttpFetch()
```

- [ ] **Step 8: Run runner tests**

```bash
cd services/scraper && uv run pytest tests/test_runner.py -v
```

Expected: both runner tests `PASS`.

- [ ] **Step 9: Run full suite**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add src/scraper/client.py src/scraper/runner.py tests/test_client.py tests/test_runner.py
git commit -m "feat(scraper): add submit_detail_result to BackendClient; refactor runner into _run_list/_run_detail"
```

---

## Task 10 — Scraper: VastgoedNL `scrape_detail`

> **Pre-step (manual):** Open a real VastgoedNL detail page in your browser (e.g. `https://aanbod.vastgoednederland.nl/koopwoningen/<any-listing>/`) and use DevTools (F12 → Inspector) to identify the CSS selectors for: asking price, status badge/label, surface area (m²), bedroom count, bathroom count, total room count, construction year/period, and energy label. Note the selectors — you will use them in Step 4.

**Files:**
- Modify: `services/scraper/src/scraper/scrapers/vastgoed_nl.py`
- Create: `services/scraper/tests/data/vastgoed_nl_detail.html`
- Modify: `services/scraper/tests/conftest.py`
- Modify: `services/scraper/tests/scrapers/test_vastgoed_nl.py`

- [ ] **Step 1: Capture an HTML fixture**

Navigate to a real VastgoedNL detail listing. In DevTools console run:
```javascript
copy(document.documentElement.outerHTML)
```
Paste the result into `services/scraper/tests/data/vastgoed_nl_detail.html`. Note the exact values on the page for all 8 fields — you'll assert these in the test.

- [ ] **Step 2: Register the fixture URL in `tests/conftest.py`**

Add an entry to `URL_TO_FILE` for the detail page URL you used:

```python
URL_TO_FILE = {
    # ... existing entries ...
    "https://aanbod.vastgoednederland.nl/koopwoningen/<your-listing-slug>/": "vastgoed_nl_detail.html",
}
```

Replace `<your-listing-slug>` with the actual path from your captured page.

- [ ] **Step 3: Write a failing test in `tests/scrapers/test_vastgoed_nl.py`**

```python
def test_scrape_detail_returns_detail_listing(vastgoed_nl_scraper):
    from scraper.models import DetailListing

    # Replace the URL below with the one you added to URL_TO_FILE
    result = vastgoed_nl_scraper.scrape_detail(
        "https://aanbod.vastgoednederland.nl/koopwoningen/<your-listing-slug>/"
    )

    assert isinstance(result, DetailListing)
    # Replace these values with what you actually see on the captured page:
    assert result.price == "€ 350.000 k.k."
    assert result.surface_area_m2 == 85
    assert result.bedroom_count == 3
    assert result.bathroom_count == 1
    assert result.room_count == 4
    assert result.construction_period == "1970-1980"
    assert result.energy_label == "C"


def test_scrape_detail_returns_none_for_absent_fields(vastgoed_nl_scraper, monkeypatch):
    """When optional fields are missing from the HTML, they come back as None."""
    from scraper.models import DetailListing

    monkeypatch.setattr(
        vastgoed_nl_scraper,
        "get_soup",
        lambda url: __import__("bs4", fromlist=["BeautifulSoup"]).BeautifulSoup(
            "<html><body><span class='price'>€ 200.000 k.k.</span></body></html>",
            "html.parser",
        ),
    )
    result = vastgoed_nl_scraper.scrape_detail("https://aanbod.vastgoednederland.nl/any/")

    assert isinstance(result, DetailListing)
    assert result.price == "€ 200.000 k.k."
    assert result.surface_area_m2 is None
    assert result.bedroom_count is None
```

- [ ] **Step 4: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_vastgoed_nl.py::test_scrape_detail_returns_detail_listing -v
```

Expected: `FAILED` — `AttributeError: 'VastgoedNLScraper' object has no attribute 'scrape_detail'`.

- [ ] **Step 5: Implement `scrape_detail` in `scrapers/vastgoed_nl.py`**

Add import at top: `from scraper.models import DetailListing`

Add the method inside `VastgoedNLScraper` (after `scrape_list`):

```python
def scrape_detail(self, url: str) -> DetailListing:
    soup = self.get_soup(url)
    return self._parse_detail_page(soup)

def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
    # Replace the CSS selectors below with the ones you identified in DevTools.

    price_el = soup.select_one("<PRICE_SELECTOR>")
    price = price_el.get_text(strip=True) if price_el else ""

    status_el = soup.select_one("<STATUS_SELECTOR>")
    from scraper.status import detect_status
    status = detect_status(status_el.get_text(strip=True) if status_el else "")

    surface_el = soup.select_one("<SURFACE_AREA_SELECTOR>")
    surface_area_m2 = _parse_int(surface_el.get_text(strip=True)) if surface_el else None

    bedroom_el = soup.select_one("<BEDROOM_COUNT_SELECTOR>")
    bedroom_count = _parse_int(bedroom_el.get_text(strip=True)) if bedroom_el else None

    bathroom_el = soup.select_one("<BATHROOM_COUNT_SELECTOR>")
    bathroom_count = _parse_int(bathroom_el.get_text(strip=True)) if bathroom_el else None

    room_el = soup.select_one("<ROOM_COUNT_SELECTOR>")
    room_count = _parse_int(room_el.get_text(strip=True)) if room_el else None

    period_el = soup.select_one("<CONSTRUCTION_PERIOD_SELECTOR>")
    construction_period = period_el.get_text(strip=True) if period_el else None

    label_el = soup.select_one("<ENERGY_LABEL_SELECTOR>")
    energy_label = label_el.get_text(strip=True).upper() if label_el else None

    return DetailListing(
        price=price,
        status=status,
        surface_area_m2=surface_area_m2,
        bedroom_count=bedroom_count,
        bathroom_count=bathroom_count,
        room_count=room_count,
        construction_period=construction_period,
        energy_label=energy_label,
    )
```

Add the private helper before the class (or as a module-level function):

```python
def _parse_int(text: str) -> int | None:
    """Extract the first integer from a string like '85 m²' or '3 kamers'."""
    import re
    match = re.search(r"\d+", text)
    return int(match.group()) if match else None
```

- [ ] **Step 6: Run VastgoedNL detail tests**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_vastgoed_nl.py -v
```

Expected: all tests including the 2 new detail tests `PASS`.

- [ ] **Step 7: Run full suite**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/scraper/scrapers/vastgoed_nl.py tests/data/vastgoed_nl_detail.html \
        tests/conftest.py tests/scrapers/test_vastgoed_nl.py
git commit -m "feat(scraper): add VastgoedNL scrape_detail with HTML fixture"
```

---

## Task 11 — Scraper: Funda `scrape_detail`

> **Pre-step (manual):** Open a real Funda detail page (e.g. `https://www.funda.nl/detail/koop/<city>/<listing>/`) and use DevTools to identify CSS selectors for: price, status, surface area (m²), bedroom count, bathroom count, total room count, construction year/period, and energy label. Note the exact values from the page for your test assertions.

**Files:**
- Modify: `services/scraper/src/scraper/scrapers/funda.py`
- Create: `services/scraper/tests/data/funda_detail.html`
- Modify: `services/scraper/tests/conftest.py`
- Modify: `services/scraper/tests/scrapers/test_funda.py`

- [ ] **Step 1: Capture an HTML fixture**

Navigate to a real Funda detail listing. In DevTools console:
```javascript
copy(document.documentElement.outerHTML)
```
Save as `services/scraper/tests/data/funda_detail.html`.

- [ ] **Step 2: Register the URL in `tests/conftest.py`**

```python
"https://www.funda.nl/detail/koop/<city>/<listing-id>/": "funda_detail.html",
```

- [ ] **Step 3: Write a failing test in `tests/scrapers/test_funda.py`**

```python
def test_scrape_detail_returns_detail_listing(funda_scraper):
    from scraper.models import DetailListing

    result = funda_scraper.scrape_detail(
        "https://www.funda.nl/detail/koop/<city>/<listing-id>/"
    )

    assert isinstance(result, DetailListing)
    # Replace values with what you see on your captured page:
    assert result.price == "€ 425.000 k.k."
    assert result.surface_area_m2 == 82
    assert result.bedroom_count == 3
    assert result.bathroom_count == 1
    assert result.room_count == 5
    assert result.construction_period == "1970-1980"
    assert result.energy_label == "C"


def test_scrape_detail_returns_none_for_absent_fields(funda_scraper, monkeypatch):
    from scraper.models import DetailListing

    monkeypatch.setattr(
        funda_scraper,
        "get_soup",
        lambda url: __import__("bs4", fromlist=["BeautifulSoup"]).BeautifulSoup(
            "<html><body><span class='price'>€ 300.000 k.k.</span></body></html>",
            "html.parser",
        ),
    )
    result = funda_scraper.scrape_detail("https://www.funda.nl/detail/any/")

    assert isinstance(result, DetailListing)
    assert result.price == "€ 300.000 k.k."
    assert result.surface_area_m2 is None
    assert result.bedroom_count is None
```

- [ ] **Step 4: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_funda.py::test_scrape_detail_returns_detail_listing -v
```

Expected: `FAILED` — `KeyError: No mock defined for URL` (fixture not yet recognized) or `AttributeError`.

- [ ] **Step 5: Implement `scrape_detail` in `scrapers/funda.py`**

Add import: `from scraper.models import DetailListing`

```python
def scrape_detail(self, url: str) -> DetailListing:
    soup = self.get_soup(url)
    return self._parse_detail_page(soup)

def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
    # Replace each selector with what you found in DevTools on the Funda detail page.

    price_el = soup.select_one("<PRICE_SELECTOR>")
    price = price_el.get_text(strip=True) if price_el else ""

    status_el = soup.select_one("<STATUS_SELECTOR>")
    from scraper.status import detect_status
    status = detect_status(status_el.get_text(strip=True) if status_el else "")

    surface_el = soup.select_one("<SURFACE_AREA_SELECTOR>")
    surface_area_m2 = _parse_int(surface_el.get_text(strip=True)) if surface_el else None

    bedroom_el = soup.select_one("<BEDROOM_COUNT_SELECTOR>")
    bedroom_count = _parse_int(bedroom_el.get_text(strip=True)) if bedroom_el else None

    bathroom_el = soup.select_one("<BATHROOM_COUNT_SELECTOR>")
    bathroom_count = _parse_int(bathroom_el.get_text(strip=True)) if bathroom_el else None

    room_el = soup.select_one("<ROOM_COUNT_SELECTOR>")
    room_count = _parse_int(room_el.get_text(strip=True)) if room_el else None

    period_el = soup.select_one("<CONSTRUCTION_PERIOD_SELECTOR>")
    construction_period = period_el.get_text(strip=True) if period_el else None

    label_el = soup.select_one("<ENERGY_LABEL_SELECTOR>")
    energy_label = label_el.get_text(strip=True).upper() if label_el else None

    return DetailListing(
        price=price,
        status=status,
        surface_area_m2=surface_area_m2,
        bedroom_count=bedroom_count,
        bathroom_count=bathroom_count,
        room_count=room_count,
        construction_period=construction_period,
        energy_label=energy_label,
    )
```

> `_parse_int` is the same helper from Task 10 — extract it to `scrapers/base.py` if you prefer to avoid duplication:
> ```python
> # In BaseScraper or as a module-level helper in each scraper file:
> import re
> def _parse_int(text: str) -> int | None:
>     match = re.search(r"\d+", text)
>     return int(match.group()) if match else None
> ```

- [ ] **Step 6: Run Funda detail tests**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_funda.py -v
```

Expected: all tests `PASS`.

- [ ] **Step 7: Run full suite**

```bash
cd services/scraper && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add src/scraper/scrapers/funda.py tests/data/funda_detail.html \
        tests/conftest.py tests/scrapers/test_funda.py
git commit -m "feat(scraper): add Funda scrape_detail with HTML fixture"
```

---

## Task 12 — Scraper: Pararius `scrape_detail`

> **Pre-step (manual):** Open a real Pararius detail page (e.g. `https://www.pararius.nl/huis-te-koop/<city>/<listing-id>/`) and use DevTools to identify CSS selectors for all 8 fields (same list as Task 10).

**Files:**
- Modify: `services/scraper/src/scraper/scrapers/pararius.py`
- Create: `services/scraper/tests/data/pararius_detail.html`
- Modify: `services/scraper/tests/conftest.py`
- Modify: `services/scraper/tests/scrapers/test_pararius.py`

- [ ] **Step 1: Capture an HTML fixture**

Navigate to a real Pararius detail listing. In DevTools:
```javascript
copy(document.documentElement.outerHTML)
```
Save as `services/scraper/tests/data/pararius_detail.html`.

- [ ] **Step 2: Register the URL in `tests/conftest.py`**

```python
"https://www.pararius.nl/huis-te-koop/<city>/<listing-id>/": "pararius_detail.html",
```

- [ ] **Step 3: Write a failing test in `tests/scrapers/test_pararius.py`**

```python
def test_scrape_detail_returns_detail_listing(pararius_scraper):
    from scraper.models import DetailListing

    result = pararius_scraper.scrape_detail(
        "https://www.pararius.nl/huis-te-koop/<city>/<listing-id>/"
    )

    assert isinstance(result, DetailListing)
    # Replace with actual values from your captured page:
    assert result.price == "€ 695.000 k.k."
    assert result.surface_area_m2 == 120
    assert result.bedroom_count == 4
    assert result.bathroom_count == 2
    assert result.room_count == 6
    assert result.construction_period == "1985-1990"
    assert result.energy_label == "B"


def test_scrape_detail_returns_none_for_absent_fields(pararius_scraper, monkeypatch):
    from scraper.models import DetailListing

    monkeypatch.setattr(
        pararius_scraper,
        "get_soup",
        lambda url: __import__("bs4", fromlist=["BeautifulSoup"]).BeautifulSoup(
            "<html><body><span class='listing-detail-summary__price'>€ 500.000 k.k.</span></body></html>",
            "html.parser",
        ),
    )
    result = pararius_scraper.scrape_detail("https://www.pararius.nl/huis-te-koop/any/")

    assert isinstance(result, DetailListing)
    assert result.price == "€ 500.000 k.k."
    assert result.surface_area_m2 is None
    assert result.bedroom_count is None
```

- [ ] **Step 4: Run to confirm failure**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_pararius.py::test_scrape_detail_returns_detail_listing -v
```

Expected: `FAILED` — `KeyError` or `AttributeError`.

- [ ] **Step 5: Implement `scrape_detail` in `scrapers/pararius.py`**

Add import: `from scraper.models import DetailListing`

```python
def scrape_detail(self, url: str) -> DetailListing:
    soup = self.get_soup(url)
    return self._parse_detail_page(soup)

def _parse_detail_page(self, soup: BeautifulSoup) -> DetailListing:
    # Replace each selector with what you found in DevTools on the Pararius detail page.

    price_el = soup.select_one("<PRICE_SELECTOR>")
    price = price_el.get_text(strip=True) if price_el else ""

    status_el = soup.select_one("<STATUS_SELECTOR>")
    from scraper.status import detect_status
    status = detect_status(status_el.get_text(strip=True) if status_el else "")

    surface_el = soup.select_one("<SURFACE_AREA_SELECTOR>")
    surface_area_m2 = _parse_int(surface_el.get_text(strip=True)) if surface_el else None

    bedroom_el = soup.select_one("<BEDROOM_COUNT_SELECTOR>")
    bedroom_count = _parse_int(bedroom_el.get_text(strip=True)) if bedroom_el else None

    bathroom_el = soup.select_one("<BATHROOM_COUNT_SELECTOR>")
    bathroom_count = _parse_int(bathroom_el.get_text(strip=True)) if bathroom_el else None

    room_el = soup.select_one("<ROOM_COUNT_SELECTOR>")
    room_count = _parse_int(room_el.get_text(strip=True)) if room_el else None

    period_el = soup.select_one("<CONSTRUCTION_PERIOD_SELECTOR>")
    construction_period = period_el.get_text(strip=True) if period_el else None

    label_el = soup.select_one("<ENERGY_LABEL_SELECTOR>")
    energy_label = label_el.get_text(strip=True).upper() if label_el else None

    return DetailListing(
        price=price,
        status=status,
        surface_area_m2=surface_area_m2,
        bedroom_count=bedroom_count,
        bathroom_count=bathroom_count,
        room_count=room_count,
        construction_period=construction_period,
        energy_label=energy_label,
    )
```

- [ ] **Step 6: Run Pararius detail tests**

```bash
cd services/scraper && uv run pytest tests/scrapers/test_pararius.py -v
```

Expected: all tests `PASS`.

- [ ] **Step 7: Run full suite for both services**

```bash
cd services/scraper && uv run pytest tests/ -v
cd services/api && uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 8: Run pre-commit checks on both services**

```bash
cd services/scraper && make pre-commit
cd services/api && make pre-commit
```

- [ ] **Step 9: Commit**

```bash
git add src/scraper/scrapers/pararius.py tests/data/pararius_detail.html \
        tests/conftest.py tests/scrapers/test_pararius.py
git commit -m "feat(scraper): add Pararius scrape_detail with HTML fixture"
```
