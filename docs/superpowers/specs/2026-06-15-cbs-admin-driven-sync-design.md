# CBS Data Sync — Admin-Driven Drill-Down

Supersedes: `2026-06-14-cbs-periodic-sync-refactor.md`

## Problem

The current `sync_cbs_data` Celery task is a monolith that iterates all ~342 Dutch municipalities, fetching hierarchy, stats, and geometry for each in a single 2-hour run. There is no visibility into what succeeded or failed, no ability to target specific entities, and the all-or-nothing approach makes debugging impossible.

## Solution

Replace the monolithic sync with an admin-driven drill-down workflow. The Django admin becomes the control plane — the user manually drives data ingestion step by step, with full visibility at each level.

### Workflow

```
1. Click "Sync All Cities" → populates City table (code + name only)
2. Select cities → action: "Fetch geo shapes" | "Fetch stats" | "Fetch districts"
3. "Fetch districts" populates District table for selected cities (code + name only)
4. Select districts → action: "Fetch geo shapes" | "Fetch stats" | "Fetch neighbourhoods"
5. "Fetch neighbourhoods" populates Neighbourhood table (code + name only)
6. Select neighbourhoods → action: "Fetch geo shapes" | "Fetch stats"
```

All actions run synchronously — the admin page waits for the CBS/PDOK API calls to complete.

## CBS Client Module (`scraping/services/cbs.py`)

Complete rewrite. Pure functions that fetch data and return it — no DB writes. The admin layer handles persistence.

### Hierarchy Functions

| Function | API Source | Returns |
|----------|-----------|---------|
| `fetch_all_cities()` | PDOK gebiedsindelingen `gemeente_gegeneraliseerd` | `list[dict]` — `[{code, name}, ...]` (~342 items) |
| `fetch_districts_for_city(city_code)` | CBS WFS `wijken`, CQL_FILTER by `gemeentecode` | `list[dict]` — `[{code, name}, ...]` |
| `fetch_neighbourhoods_for_district(district_code)` | CBS WFS `buurten`, CQL_FILTER by `wijkcode` | `list[dict]` — `[{code, name}, ...]` |

### Geometry Functions

| Function | API Source | Returns |
|----------|-----------|---------|
| `fetch_city_geometry(city_code)` | PDOK gebiedsindelingen filtered by code | `list[list[list[list[float]]]]` (MultiPolygon coords) |
| `fetch_district_geometry(district_code)` | CBS WFS `wijken`, CQL_FILTER by `wijkcode` | same format |
| `fetch_neighbourhood_geometry(neighbourhood_code)` | CBS WFS `buurten`, CQL_FILTER by `buurtcode` | same format |

### Stats Functions

| Function | API Source | Returns |
|----------|-----------|---------|
| `fetch_city_stats(city_code)` | CBS WFS `gemeenten`, primary + backfill year | `tuple[dict, int]` — `(cleaned_stats, year)` |
| `fetch_district_stats(district_code)` | CBS WFS `wijken`, primary + backfill year | same |
| `fetch_neighbourhood_stats(neighbourhood_code)` | CBS WFS `buurten`, primary + backfill year | same |

Stats functions make two API calls: primary year (2024) first, then secondary year (2023) to backfill 7 income/wealth/age fields where primary has sentinel values.

### Internal Helpers (carried from current code)

- `_wfs_get(type_name, year, cql_filter, ...)` — httpx GET with exponential-backoff retry (6 attempts, up to 20s delay). Signature changes: replaces `bbox` parameter with `cql_filter`.
- `_clean_stats(properties)` — strips CBS sentinel values (`-99997`, `-99998`, `-99999998`, `-99999997`) to `None`.
- `_extract_geometry(geom)` — normalizes Polygon/MultiPolygon to internal `list[list[list[list[float]]]]` format, rounded to 5 decimal places.
- `_merge_backfill(primary_stats, secondary_stats)` — fills `None` fields from secondary year for the 7 backfill fields.

### Constants

```python
PRIMARY_YEAR = 2024
BACKFILL_YEAR = 2023
CBS_SENTINEL_VALUES = {-99997, -99998, -99999998, -99999997}
BACKFILL_FIELDS = [...]  # 7 income/wealth/age field names (carried from current code)
PDOK_GEBIEDSINDELINGEN_URL = "https://api.pdok.nl/cbs/gebiedsindelingen/ogc/v1/collections/gemeente_gegeneraliseerd/items"
CBS_WFS_URL_TEMPLATE = "https://service.pdok.nl/cbs/wijkenbuurten/{year}/wfs/v1_0"
```

## Django Admin Integration

### CityAdmin

**Custom changelist button: "Sync All Cities"**

A custom button rendered at the top of the City list page. Implemented as a custom admin URL (`/admin/scraping/city/sync-cities/`) that calls `fetch_all_cities()`, does `update_or_create(code=..., defaults={name=...})` for each city, and redirects back to the changelist with a success message.

**Admin actions on selected cities:**

| Action | Behavior |
|--------|----------|
| Fetch geo shapes | For each selected city: `fetch_city_geometry(code)` → save to `city.geometry`, set `geometry_fetched_at` |
| Fetch stats | For each: `fetch_city_stats(code)` → save to `city.stats` + `city.stats_year`, set `stats_fetched_at` |
| Fetch districts | For each: `fetch_districts_for_city(code)` → `District.update_or_create(code=..., defaults={name=..., city=city})` |

### DistrictAdmin

**Admin actions on selected districts:**

| Action | Behavior |
|--------|----------|
| Fetch geo shapes | `fetch_district_geometry(code)` → save geometry, set `geometry_fetched_at` |
| Fetch stats | `fetch_district_stats(code)` → save stats + stats_year, set `stats_fetched_at` |
| Fetch neighbourhoods | `fetch_neighbourhoods_for_district(code)` → `Neighborhood.update_or_create(code=..., defaults={name=..., district=district, city=district.city})` |

### NeighborhoodAdmin

**Admin actions on selected neighbourhoods:**

| Action | Behavior |
|--------|----------|
| Fetch geo shapes | `fetch_neighbourhood_geometry(code)` → save geometry, set `geometry_fetched_at` |
| Fetch stats | `fetch_neighbourhood_stats(code)` → save stats + stats_year, set `stats_fetched_at` |

### Feedback

All actions use Django admin messages:
- Success: "Fetched stats for 5 cities."
- Partial failure: "Fetched stats for 3 cities. Failed: 0518 (timeout), 0363 (not found)."
- Full failure: "Failed to fetch stats for all 2 cities: 0518 (timeout), 0363 (not found)."

### List Display Enhancements

All three admin classes show indicator columns:
- **Has geometry** — boolean icon based on `geometry is not None`
- **Has stats** — boolean icon based on `stats is not None`
- **Geometry fetched at** — timestamp
- **Stats fetched at** — timestamp

This gives immediate visibility into which entities still need enrichment.

## Model Changes

### Migration: split `fetched_at` into two timestamps

On all three models (`City`, `District`, `Neighborhood`):

| Remove | Add |
|--------|-----|
| `fetched_at` (DateTimeField, nullable) | `geometry_fetched_at` (DateTimeField, nullable) |
| | `stats_fetched_at` (DateTimeField, nullable) |

The existing `fetched_at` data is ambiguous (could mean either), so it will be dropped rather than copied.

All other fields remain unchanged: `code`, `name`, `geometry` (JSONField nullable), `stats` (JSONField nullable), `stats_year`, `created_at`, `updated_at`.

## Cleanup

### Removed

| Item | Location |
|------|----------|
| `sync_cbs_data` task | `scraping/tasks.py` |
| Entire current `cbs.py` implementation | `scraping/services/cbs.py` (replaced with rewrite) |
| `test_cbs_fetcher.py` | `tests/test_cbs_fetcher.py` (replaced with new tests) |

### Kept As-Is

| Item | Location | Reason |
|------|----------|--------|
| API endpoints | `scraping/api.py` | Pure DB reads, unaffected |
| API schemas | `scraping/schemas.py` | Response shapes unchanged |
| Test factories | `tests/factories.py` | May need minor field updates for timestamp split |
| Endpoint tests | `tests/test_cities.py`, `test_stats.py`, `test_shapes.py` | May need minor updates for timestamp field rename |

## Testing

### CBS Client Tests (`tests/test_cbs_client.py`)

Mock httpx calls at the transport level. For each public function:
- Verify correct API URL and parameters (CQL_FILTER values, year, etc.)
- Verify correct parsing of API response into return format
- Verify error handling (HTTP errors, malformed responses)
- For stats functions: verify backfill merge logic (primary has gaps → secondary fills them)
- For geometry functions: verify Polygon/MultiPolygon normalization

### Admin Action Tests (`tests/test_cbs_admin.py`)

Use test factories to create model instances. Mock CBS client functions (not HTTP — mock at the function boundary).
- Verify each action calls the correct CBS function with the right arguments
- Verify DB persistence (geometry, stats, timestamps updated)
- Verify success/failure messaging
- Verify the "Sync All Cities" custom button creates/updates City records
- Verify "Fetch districts" creates District records linked to the correct city
- Verify "Fetch neighbourhoods" creates Neighbourhood records linked to correct district and city

### Existing Tests

- `test_cities.py`, `test_stats.py`, `test_shapes.py` — update factory calls if `fetched_at` → `geometry_fetched_at`/`stats_fetched_at` changes affect them. Endpoint behavior is unchanged.

## Files Changed

| File | Change |
|------|--------|
| `scraping/services/cbs.py` | Complete rewrite — focused pure functions |
| `scraping/admin.py` | Expand with admin actions, custom sync button, list display |
| `scraping/models.py` | Split `fetched_at` into `geometry_fetched_at` + `stats_fetched_at` |
| `scraping/tasks.py` | Remove `sync_cbs_data` task |
| `scraping/migrations/0018_*.py` | New migration for timestamp split |
| `tests/test_cbs_fetcher.py` | Remove (replaced by new test files) |
| `tests/test_cbs_client.py` | New — CBS client function tests |
| `tests/test_cbs_admin.py` | New — admin action tests |
| `tests/factories.py` | Update timestamp fields |
| `tests/test_cities.py` | Minor updates for timestamp field rename if needed |
| `tests/test_stats.py` | Minor updates if needed |
| `tests/test_shapes.py` | Minor updates if needed |

## Risks

**CQL_FILTER on CBS WFS:** The current code uses bbox (bounding box) filtering. This design switches to CQL_FILTER (e.g., `gemeentecode='GM0518'`). If CQL_FILTER is not supported or unreliable on the CBS WFS endpoint, the fallback is to fetch the parent entity's geometry first, compute a bbox, and use bbox filtering as before. This would require fetching city geometry before fetching districts (adding a dependency between actions), and would need testing during implementation.

## Verification

```bash
cd services/api && uv run pytest tests/ -v
make lint
```
