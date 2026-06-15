# CBS Admin-Driven Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the monolithic `sync_cbs_data` Celery task with admin-driven drill-down actions: sync cities, then selectively fetch districts/neighbourhoods/stats/geometry per entity via Django admin.

**Architecture:** Pure CBS client functions (no DB writes) in `cbs.py` return data; Django admin actions call these functions and persist results. The admin becomes the control plane — all data ingestion is manually triggered with full visibility.

**Tech Stack:** Django 5.x, httpx, respx (test mocking), pytest, factory_boy

**Spec:** `docs/superpowers/specs/2026-06-15-cbs-admin-driven-sync-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `scraping/models.py` | Modify (lines 179–233) | Split `fetched_at` → `geometry_fetched_at` + `stats_fetched_at` on all 3 models |
| `scraping/migrations/0018_split_fetched_at.py` | Create | Migration for the timestamp split |
| `scraping/services/cbs.py` | Rewrite | Pure functions: 3 hierarchy + 3 geometry + 3 stats + helpers |
| `scraping/admin.py` | Modify (lines 364–387) | Expand 3 admin classes with actions + custom sync button |
| `scraping/templates/admin/scraping/city/change_list.html` | Create | Template for "Sync All Cities" button |
| `scraping/tasks.py` | Modify (lines 1–17, 212–240) | Remove `sync_cbs_data` task + CBS imports |
| `tests/test_cbs_client.py` | Create | Tests for all 9 public CBS client functions + helpers |
| `tests/test_cbs_admin.py` | Create | Tests for all admin actions |
| `tests/test_cbs_fetcher.py` | Delete | Replaced by `test_cbs_client.py` |
| `tests/factories.py` | Modify | Update `fetched_at` → new timestamp fields |
| `tests/conftest.py` | Modify | Add `admin_client` fixture |

---

### Task 1: Model Migration — Split `fetched_at`

**Files:**
- Modify: `scraping/models.py:179-233`
- Create: `scraping/migrations/0018_split_fetched_at.py`
- Modify: `tests/factories.py`

- [ ] **Step 1: Update City model**

In `scraping/models.py`, replace the `fetched_at` field on `City` (line 185):

```python
# Before (line 185):
fetched_at = models.DateTimeField(null=True, blank=True)

# After:
geometry_fetched_at = models.DateTimeField(null=True, blank=True)
stats_fetched_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 2: Update District model**

Same replacement on `District` (line 204):

```python
# Before:
fetched_at = models.DateTimeField(null=True, blank=True)

# After:
geometry_fetched_at = models.DateTimeField(null=True, blank=True)
stats_fetched_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 3: Update Neighborhood model**

Same replacement on `Neighborhood` (line 225):

```python
# Before:
fetched_at = models.DateTimeField(null=True, blank=True)

# After:
geometry_fetched_at = models.DateTimeField(null=True, blank=True)
stats_fetched_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: Generate migration**

Run:
```bash
cd services/api && uv run python manage.py makemigrations scraping -n split_fetched_at
```

Expected: Creates `scraping/migrations/0018_split_fetched_at.py` that removes `fetched_at` and adds `geometry_fetched_at` + `stats_fetched_at` on all three models.

- [ ] **Step 5: Apply migration**

Run:
```bash
cd services/api && uv run python manage.py migrate
```

Expected: `Applying scraping.0018_split_fetched_at... OK`

- [ ] **Step 6: Run existing tests to see what breaks**

Run:
```bash
cd services/api && uv run pytest tests/ -v 2>&1 | head -80
```

Expected: Some tests will fail referencing `fetched_at`. Note which tests fail — they'll be fixed in the cleanup task. The model migration itself is correct.

- [ ] **Step 7: Commit**

```bash
git add scraping/models.py scraping/migrations/0018_*.py
git commit -m "$(cat <<'EOF'
Services|Refactor: split fetched_at into geometry_fetched_at and stats_fetched_at
EOF
)"
```

---

### Task 2: CBS Client — Rewrite with Pure Functions

**Files:**
- Create: `tests/test_cbs_client.py`
- Rewrite: `scraping/services/cbs.py`

This task rewrites `cbs.py` from scratch. The new module has 9 public functions (3 hierarchy, 3 geometry, 3 stats) that return pure data — no DB writes. Internal helpers (`_wfs_get`, `_clean_stats`, `_extract_geometry`, `_merge_backfill`) are carried forward with minor signature changes.

- [ ] **Step 1: Write tests for internal helpers**

Create `tests/test_cbs_client.py`:

```python
from __future__ import annotations

import httpx
import pytest
import respx

from scraping.services.cbs import (
    CBS_PRIMARY_YEAR,
    CBS_SECONDARY_YEAR,
    CBS_WFS_URL,
    _GEMEENTE_GEOMETRY_URL,
    _clean_stats,
    _extract_geometry,
    _merge_backfill,
    _wfs_get,
)


class TestCleanStats:
    def test_strips_sentinel_values(self):
        raw = {"woz": 350, "inkomen": -99997, "vermogen": -99998}
        result = _clean_stats(raw)
        assert result["woz"] == 350
        assert result["inkomen"] is None
        assert result["vermogen"] is None

    def test_strips_large_negative_sentinels(self):
        result = _clean_stats({"val": -99999998})
        assert result["val"] is None

    def test_preserves_valid_negative_values(self):
        result = _clean_stats({"val": -5, "other": -100})
        assert result["val"] == -5
        assert result["other"] == -100

    def test_preserves_non_numeric_values(self):
        result = _clean_stats({"name": "Amsterdam", "val": None})
        assert result["name"] == "Amsterdam"
        assert result["val"] is None


class TestExtractGeometry:
    def test_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[4.123456789, 52.123456789], [4.2, 52.0], [4.3, 52.1], [4.123456789, 52.123456789]]],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert result[0][0][0] == [4.12346, 52.12346]

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]],
                [[[5.0, 53.0], [5.1, 53.0], [5.1, 53.1], [5.0, 53.0]]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 2

    def test_unsupported_type_returns_empty(self):
        assert _extract_geometry({"type": "Point", "coordinates": [4.0, 52.0]}) == []


class TestMergeBackfill:
    def test_fills_none_from_secondary(self):
        primary = {"gemiddeldInkomenPerInwoner": None, "woz": 350}
        secondary = {"gemiddeldInkomenPerInwoner": 28000, "woz": 340}
        result = _merge_backfill(primary, secondary)
        assert result["gemiddeldInkomenPerInwoner"] == 28000
        assert result["woz"] == 350

    def test_no_secondary_returns_primary(self):
        primary = {"gemiddeldInkomenPerInwoner": None, "woz": 350}
        result = _merge_backfill(primary, None)
        assert result["gemiddeldInkomenPerInwoner"] is None

    def test_does_not_overwrite_existing_values(self):
        primary = {"gemiddeldInkomenPerInwoner": 30000}
        secondary = {"gemiddeldInkomenPerInwoner": 28000}
        result = _merge_backfill(primary, secondary)
        assert result["gemiddeldInkomenPerInwoner"] == 30000


class TestWfsGet:
    @respx.mock
    def test_returns_features(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        feature = {"type": "Feature", "properties": {"code": "WK001"}, "geometry": None}
        respx.get(url).mock(return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": [feature]}))
        result = _wfs_get("wijkenbuurten:wijken", cql_filter="gemeentecode='GM0518'")
        assert len(result) == 1
        assert result[0]["properties"]["code"] == "WK001"

    @respx.mock
    def test_retries_on_server_error(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        route = respx.get(url).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json={"type": "FeatureCollection", "features": []}),
            ]
        )
        result = _wfs_get("wijkenbuurten:wijken", max_retries=2, initial_delay=0.01)
        assert result == []
        assert route.call_count == 2

    @respx.mock
    def test_raises_after_max_retries(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(500))
        with pytest.raises(RuntimeError, match="CBS WFS request failed"):
            _wfs_get("wijkenbuurten:wijken", max_retries=2, initial_delay=0.01)
```

- [ ] **Step 2: Write tests for hierarchy functions**

Append to `tests/test_cbs_client.py`:

```python
from scraping.services.cbs import (
    fetch_all_cities,
    fetch_districts_for_city,
    fetch_neighbourhoods_for_district,
)


def _pdok_gemeente_response(*cities):
    """Build a PDOK gebiedsindelingen FeatureCollection."""
    features = []
    for code, name in cities:
        features.append({
            "type": "Feature",
            "properties": {"statcode": f"GM{code}", "statnaam": name},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]},
        })
    return {"type": "FeatureCollection", "features": features}


def _wfs_fc(*features):
    """Wrap features in a FeatureCollection HTTP response."""
    return httpx.Response(200, json={"type": "FeatureCollection", "features": list(features)})


def _wijk_feature(code, name, gm_code):
    return {
        "type": "Feature",
        "properties": {"wijkcode": code, "wijknaam": name, "gemeentecode": gm_code},
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


def _buurt_feature(code, name, wijk_code):
    return {
        "type": "Feature",
        "properties": {"buurtcode": code, "buurtnaam": name, "wijkcode": wijk_code},
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


class TestFetchAllCities:
    @respx.mock
    def test_returns_code_and_name(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "'s-Gravenhage"), ("0363", "Amsterdam")))
        )
        result = fetch_all_cities()
        assert len(result) == 2
        assert {"code": "0518", "name": "'s-Gravenhage"} in result
        assert {"code": "0363", "name": "Amsterdam"} in result

    @respx.mock
    def test_strips_gm_prefix(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_all_cities()
        assert result[0]["code"] == "0518"


class TestFetchDistrictsForCity:
    @respx.mock
    def test_returns_districts(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(
            _wijk_feature("WK051801", "Centrum", "GM0518"),
            _wijk_feature("WK051802", "Escamp", "GM0518"),
        ))
        result = fetch_districts_for_city("0518")
        assert len(result) == 2
        assert {"code": "WK051801", "name": "Centrum"} in result

    @respx.mock
    def test_empty_result(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        result = fetch_districts_for_city("9999")
        assert result == []


class TestFetchNeighbourhoodsForDistrict:
    @respx.mock
    def test_returns_neighbourhoods(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(
            _buurt_feature("BU05180100", "Schilderswijk-West", "WK051801"),
            _buurt_feature("BU05180101", "Schilderswijk-Oost", "WK051801"),
        ))
        result = fetch_neighbourhoods_for_district("WK051801")
        assert len(result) == 2
        assert {"code": "BU05180100", "name": "Schilderswijk-West"} in result
```

- [ ] **Step 3: Write tests for geometry functions**

Append to `tests/test_cbs_client.py`:

```python
from scraping.services.cbs import (
    fetch_city_geometry,
    fetch_district_geometry,
    fetch_neighbourhood_geometry,
)


class TestFetchCityGeometry:
    @respx.mock
    def test_returns_geometry(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_city_geometry("0518")
        assert len(result) == 1
        assert len(result[0]) == 1  # one ring
        assert len(result[0][0]) == 4  # 4 points

    @respx.mock
    def test_raises_for_unknown_city(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        with pytest.raises(ValueError, match="City 9999 not found"):
            fetch_city_geometry("9999")


class TestFetchDistrictGeometry:
    @respx.mock
    def test_returns_geometry(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(_wijk_feature("WK051801", "Centrum", "GM0518")))
        result = fetch_district_geometry("WK051801")
        assert len(result) == 1

    @respx.mock
    def test_raises_for_unknown_district(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="District WK999999 not found"):
            fetch_district_geometry("WK999999")


class TestFetchNeighbourhoodGeometry:
    @respx.mock
    def test_returns_geometry(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(_buurt_feature("BU05180100", "Schilderswijk", "WK051801")))
        result = fetch_neighbourhood_geometry("BU05180100")
        assert len(result) == 1

    @respx.mock
    def test_raises_for_unknown_neighbourhood(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="Neighbourhood BU99999999 not found"):
            fetch_neighbourhood_geometry("BU99999999")
```

- [ ] **Step 4: Write tests for stats functions**

Append to `tests/test_cbs_client.py`:

```python
from scraping.services.cbs import (
    fetch_city_stats,
    fetch_district_stats,
    fetch_neighbourhood_stats,
)


def _gemeente_feature(code, **stats):
    props = {"gemeentecode": code, "gemeentenaam": "Test", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "MultiPolygon", "coordinates": [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]},
    }


def _wijk_stats_feature(code, **stats):
    props = {"wijkcode": code, "wijknaam": "Test", "gemeentecode": "GM0518", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


def _buurt_stats_feature(code, **stats):
    props = {"buurtcode": code, "buurtnaam": "Test", "wijkcode": "WK051801", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


class TestFetchCityStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_gemeente_feature("GM0518", gemiddeldeWoningwaarde=350)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_gemeente_feature("GM0518", gemiddeldeWoningwaarde=340)))
        stats, year = fetch_city_stats("0518")
        assert stats["gemiddeldeWoningwaarde"] == 350
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_backfills_from_secondary_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(
            _gemeente_feature("GM0518", gemiddeldInkomenPerInwoner=-99997, gemiddeldeWoningwaarde=350)
        ))
        respx.get(url_secondary).mock(return_value=_wfs_fc(
            _gemeente_feature("GM0518", gemiddeldInkomenPerInwoner=28000, gemiddeldeWoningwaarde=340)
        ))
        stats, _ = fetch_city_stats("0518")
        assert stats["gemiddeldInkomenPerInwoner"] == 28000
        assert stats["gemiddeldeWoningwaarde"] == 350

    @respx.mock
    def test_raises_for_unknown_city(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for city 9999"):
            fetch_city_stats("9999")


class TestFetchDistrictStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_wijk_stats_feature("WK051801", gemiddeldeWoningwaarde=280)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_wijk_stats_feature("WK051801", gemiddeldeWoningwaarde=270)))
        stats, year = fetch_district_stats("WK051801")
        assert stats["gemiddeldeWoningwaarde"] == 280
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_raises_for_unknown_district(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for district"):
            fetch_district_stats("WK999999")


class TestFetchNeighbourhoodStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_buurt_stats_feature("BU05180100", gemiddeldeWoningwaarde=200)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_buurt_stats_feature("BU05180100", gemiddeldeWoningwaarde=190)))
        stats, year = fetch_neighbourhood_stats("BU05180100")
        assert stats["gemiddeldeWoningwaarde"] == 200
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_raises_for_unknown_neighbourhood(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for neighbourhood"):
            fetch_neighbourhood_stats("BU99999999")
```

- [ ] **Step 5: Run tests to verify they fail**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_client.py -v
```

Expected: All tests FAIL because the new functions don't exist yet in `cbs.py`.

- [ ] **Step 6: Implement the CBS client**

Rewrite `scraping/services/cbs.py` with this complete implementation:

```python
from __future__ import annotations

import time

import httpx
from loguru import logger

CBS_WFS_URL = "https://service.pdok.nl/cbs/wijkenbuurten/{year}/wfs/v1_0"
CBS_PRIMARY_YEAR = 2024
CBS_SECONDARY_YEAR = 2023
CBS_SENTINEL_VALUES = {-99997, -99998, -99999998, -99999997}
BACKFILL_FIELDS = [
    "gemiddeldInkomenPerInwoner",
    "gemiddeldInkomenPerInkomensontvanger",
    "mediaanVermogenVanParticuliereHuish",
    "percentagePersonenMetLaagInkomen",
    "percentagePersonenMetHoogInkomen",
    "percentageBouwjaarklasseTot2000",
    "percentageBouwjaarklasseVanaf2000",
]
_GEMEENTE_GEOMETRY_URL = (
    "https://api.pdok.nl/cbs/gebiedsindelingen/ogc/v1"
    "/collections/gemeente_gegeneraliseerd/items"
)


def _wfs_get(
    type_name: str,
    *,
    year: int = CBS_PRIMARY_YEAR,
    cql_filter: str | None = None,
    count: int = 4000,
    max_retries: int = 6,
    initial_delay: float = 1.0,
) -> list[dict]:
    url = CBS_WFS_URL.format(year=year)
    params: dict[str, str] = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "json",
        "srsName": "EPSG:4326",
        "count": str(count),
    }
    if cql_filter:
        params["CQL_FILTER"] = cql_filter

    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            resp = httpx.get(url, params=params, timeout=30.0)
            resp.raise_for_status()
            return resp.json().get("features", [])
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            if attempt == max_retries:
                msg = f"CBS WFS request failed after {max_retries} attempts"
                raise RuntimeError(msg) from exc
            logger.warning("CBS WFS attempt {}/{} failed: {}", attempt, max_retries, exc)
            time.sleep(delay)
            delay = min(delay * 2, 20.0)
    return []


def _clean_stats(properties: dict) -> dict:
    cleaned = {}
    for key, val in properties.items():
        if isinstance(val, (int, float)) and (val in CBS_SENTINEL_VALUES or val <= -99990):
            cleaned[key] = None
        else:
            cleaned[key] = val
    return cleaned


def _round_ring(ring: list) -> list:
    return [[round(coord, 5) for coord in point] for point in ring]


def _extract_geometry(geom: dict) -> list:
    geo_type = geom.get("type")
    coords = geom.get("coordinates", [])
    if geo_type == "Polygon":
        return [[_round_ring(ring) for ring in coords]]
    if geo_type == "MultiPolygon":
        return [[_round_ring(ring) for ring in polygon] for polygon in coords]
    return []


def _merge_backfill(primary_stats: dict, secondary_stats: dict | None) -> dict:
    if secondary_stats is None:
        return primary_stats
    for field in BACKFILL_FIELDS:
        if primary_stats.get(field) is None and secondary_stats.get(field) is not None:
            primary_stats[field] = secondary_stats[field]
    return primary_stats


# --- Hierarchy functions ---


def fetch_all_cities() -> list[dict]:
    resp = httpx.get(
        _GEMEENTE_GEOMETRY_URL,
        params={"limit": 500, "f": "json", "jaarcode": CBS_PRIMARY_YEAR},
        timeout=30.0,
    )
    resp.raise_for_status()
    return [
        {"code": f["properties"]["statcode"].removeprefix("GM"), "name": f["properties"]["statnaam"]}
        for f in resp.json()["features"]
    ]


def fetch_districts_for_city(city_code: str) -> list[dict]:
    features = _wfs_get(
        "wijkenbuurten:wijken",
        cql_filter=f"gemeentecode='GM{city_code}'",
    )
    return [
        {"code": f["properties"]["wijkcode"], "name": f["properties"]["wijknaam"]}
        for f in features
    ]


def fetch_neighbourhoods_for_district(district_code: str) -> list[dict]:
    features = _wfs_get(
        "wijkenbuurten:buurten",
        cql_filter=f"wijkcode='{district_code}'",
    )
    return [
        {"code": f["properties"]["buurtcode"], "name": f["properties"]["buurtnaam"]}
        for f in features
    ]


# --- Geometry functions ---


def fetch_city_geometry(city_code: str) -> list:
    resp = httpx.get(
        _GEMEENTE_GEOMETRY_URL,
        params={"limit": 500, "f": "json", "jaarcode": CBS_PRIMARY_YEAR},
        timeout=30.0,
    )
    resp.raise_for_status()
    for feature in resp.json()["features"]:
        code = feature["properties"]["statcode"].removeprefix("GM")
        if code == city_code:
            return _extract_geometry(feature["geometry"])
    msg = f"City {city_code} not found in PDOK response"
    raise ValueError(msg)


def fetch_district_geometry(district_code: str) -> list:
    features = _wfs_get(
        "wijkenbuurten:wijken",
        cql_filter=f"wijkcode='{district_code}'",
    )
    if not features:
        msg = f"District {district_code} not found"
        raise ValueError(msg)
    return _extract_geometry(features[0]["geometry"])


def fetch_neighbourhood_geometry(neighbourhood_code: str) -> list:
    features = _wfs_get(
        "wijkenbuurten:buurten",
        cql_filter=f"buurtcode='{neighbourhood_code}'",
    )
    if not features:
        msg = f"Neighbourhood {neighbourhood_code} not found"
        raise ValueError(msg)
    return _extract_geometry(features[0]["geometry"])


# --- Stats functions (with backfill) ---


def _fetch_stats(
    type_name: str, filter_key: str, filter_value: str, entity_label: str
) -> tuple[dict, int]:
    features = _wfs_get(type_name, cql_filter=f"{filter_key}='{filter_value}'")
    if not features:
        msg = f"No stats found for {entity_label}"
        raise ValueError(msg)
    stats = _clean_stats(features[0]["properties"])
    sec_features = _wfs_get(
        type_name,
        year=CBS_SECONDARY_YEAR,
        cql_filter=f"{filter_key}='{filter_value}'",
    )
    sec_stats = _clean_stats(sec_features[0]["properties"]) if sec_features else None
    stats = _merge_backfill(stats, sec_stats)
    return stats, CBS_PRIMARY_YEAR


def fetch_city_stats(city_code: str) -> tuple[dict, int]:
    return _fetch_stats(
        "wijkenbuurten:gemeenten", "gemeentecode", f"GM{city_code}", f"city {city_code}"
    )


def fetch_district_stats(district_code: str) -> tuple[dict, int]:
    return _fetch_stats(
        "wijkenbuurten:wijken", "wijkcode", district_code, f"district {district_code}"
    )


def fetch_neighbourhood_stats(neighbourhood_code: str) -> tuple[dict, int]:
    return _fetch_stats(
        "wijkenbuurten:buurten", "buurtcode", neighbourhood_code, f"neighbourhood {neighbourhood_code}"
    )
```

- [ ] **Step 7: Run client tests to verify they pass**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_client.py -v
```

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add scraping/services/cbs.py tests/test_cbs_client.py
git commit -m "$(cat <<'EOF'
Services|Refactor: rewrite CBS client as pure functions with no DB writes
EOF
)"
```

---

### Task 3: Admin Actions — CityAdmin

**Files:**
- Create: `tests/test_cbs_admin.py`
- Modify: `scraping/admin.py:364-387`
- Create: `scraping/templates/admin/scraping/city/change_list.html`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Add admin_client fixture**

In `tests/conftest.py`, add the `admin_client` fixture at the end of the file:

```python
from django.test import Client as DjangoTestClient


@pytest.fixture
def admin_client(db):
    from django.contrib.auth.models import User

    user = User.objects.create_superuser("admin", "admin@test.com", "testpass")
    tc = DjangoTestClient()
    tc.force_login(user)
    return tc
```

- [ ] **Step 2: Write tests for CityAdmin actions**

Create `tests/test_cbs_admin.py`:

```python
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

from scraping.models import City, District
from tests.factories import CityFactory


@pytest.mark.django_db
class TestSyncAllCities:
    def test_creates_cities(self, admin_client):
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            return_value=[
                {"code": "0518", "name": "'s-Gravenhage"},
                {"code": "0363", "name": "Amsterdam"},
            ],
        ):
            response = admin_client.post("/admin/scraping/city/sync-cities/")
        assert response.status_code == 302
        assert City.objects.count() == 2
        assert City.objects.get(code="0518").name == "'s-Gravenhage"

    def test_updates_existing_city(self, admin_client):
        CityFactory(code="0518", name="Old Name")
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            return_value=[{"code": "0518", "name": "'s-Gravenhage"}],
        ):
            admin_client.post("/admin/scraping/city/sync-cities/")
        assert City.objects.get(code="0518").name == "'s-Gravenhage"

    def test_reports_error(self, admin_client):
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            side_effect=RuntimeError("API down"),
        ):
            response = admin_client.post("/admin/scraping/city/sync-cities/")
        assert response.status_code == 302
        assert City.objects.count() == 0


@pytest.mark.django_db
class TestCityFetchGeoShapes:
    def test_saves_geometry(self, admin_client):
        city = CityFactory(code="0518")
        geometry = [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]
        with patch("scraping.admin.cbs.fetch_city_geometry", return_value=geometry):
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_geo_shapes", ACTION_CHECKBOX_NAME: [city.pk]},
            )
        city.refresh_from_db()
        assert city.geometry == geometry
        assert city.geometry_fetched_at is not None


@pytest.mark.django_db
class TestCityFetchStats:
    def test_saves_stats(self, admin_client):
        city = CityFactory(code="0518")
        with patch(
            "scraping.admin.cbs.fetch_city_stats",
            return_value=({"woz": 350}, 2024),
        ):
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_stats", ACTION_CHECKBOX_NAME: [city.pk]},
            )
        city.refresh_from_db()
        assert city.stats == {"woz": 350}
        assert city.stats_year == 2024
        assert city.stats_fetched_at is not None


@pytest.mark.django_db
class TestCityFetchDistricts:
    def test_creates_districts(self, admin_client):
        city = CityFactory(code="0518")
        with patch(
            "scraping.admin.cbs.fetch_districts_for_city",
            return_value=[
                {"code": "WK051801", "name": "Centrum"},
                {"code": "WK051802", "name": "Escamp"},
            ],
        ):
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_districts", ACTION_CHECKBOX_NAME: [city.pk]},
            )
        assert District.objects.filter(city=city).count() == 2
        assert District.objects.get(code="WK051801").name == "Centrum"
        assert District.objects.get(code="WK051801").city == city
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py -v
```

Expected: All tests FAIL — admin actions don't exist yet.

- [ ] **Step 4: Create the city changelist template**

Create the directory and template file:

```bash
mkdir -p services/api/scraping/templates/admin/scraping/city
```

Create `scraping/templates/admin/scraping/city/change_list.html`:

```html
{% extends "admin/change_list.html" %}

{% block object-tools-items %}
    <li>
        <a href="{% url 'admin:scraping_city_sync' %}" class="button">Sync All Cities</a>
    </li>
    {{ block.super }}
{% endblock %}
```

- [ ] **Step 5: Implement CityAdmin**

In `scraping/admin.py`, add import at the top (after existing imports, around line 21):

```python
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from scraping.services import cbs
```

Replace the existing `CityAdmin` class (lines 364–369) with:

```python
@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "has_geometry", "has_stats", "geometry_fetched_at", "stats_fetched_at")
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats", "fetch_districts"]
    change_list_template = "admin/scraping/city/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("sync-cities/", self.admin_site.admin_view(self.sync_cities_view), name="scraping_city_sync"),
        ]
        return custom_urls + urls

    def sync_cities_view(self, request):
        try:
            cities_data = cbs.fetch_all_cities()
            count = 0
            for city_data in cities_data:
                City.objects.update_or_create(
                    code=city_data["code"],
                    defaults={"name": city_data["name"]},
                )
                count += 1
            messages.success(request, f"Synced {count} cities.")
        except Exception as exc:
            messages.error(request, f"Failed to sync cities: {exc}")
        return HttpResponseRedirect(reverse("admin:scraping_city_changelist"))

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for city in queryset:
            try:
                city.geometry = cbs.fetch_city_geometry(city.code)
                city.geometry_fetched_at = now
                city.save(update_fields=["geometry", "geometry_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{city.code} ({exc})")
        self._report(request, "geo shapes", success, failures, "cities")

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for city in queryset:
            try:
                stats, year = cbs.fetch_city_stats(city.code)
                city.stats = stats
                city.stats_year = year
                city.stats_fetched_at = now
                city.save(update_fields=["stats", "stats_year", "stats_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{city.code} ({exc})")
        self._report(request, "stats", success, failures, "cities")

    @admin.action(description="Fetch districts")
    def fetch_districts(self, request, queryset):
        success, failures = 0, []
        for city in queryset:
            try:
                for d in cbs.fetch_districts_for_city(city.code):
                    District.objects.update_or_create(
                        code=d["code"], defaults={"name": d["name"], "city": city}
                    )
                success += 1
            except Exception as exc:
                failures.append(f"{city.code} ({exc})")
        self._report(request, "districts", success, failures, "cities")

    @staticmethod
    def _report(request, entity, success, failures, level_name):
        msg = f"Fetched {entity} for {success} {level_name}."
        if failures:
            msg += f" Failed: {', '.join(failures)}."
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None
```

- [ ] **Step 6: Run CityAdmin tests to verify they pass**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py -v
```

Expected: All `TestSyncAllCities`, `TestCityFetchGeoShapes`, `TestCityFetchStats`, `TestCityFetchDistricts` tests PASS.

- [ ] **Step 7: Commit**

```bash
git add scraping/admin.py scraping/templates/ tests/test_cbs_admin.py tests/conftest.py
git commit -m "$(cat <<'EOF'
Services|Add: CBS admin actions for City (sync, geo shapes, stats, districts)
EOF
)"
```

---

### Task 4: Admin Actions — DistrictAdmin

**Files:**
- Modify: `tests/test_cbs_admin.py`
- Modify: `scraping/admin.py:372-378`

- [ ] **Step 1: Write tests for DistrictAdmin actions**

Append to `tests/test_cbs_admin.py`:

```python
from scraping.models import Neighborhood
from tests.factories import DistrictFactory


@pytest.mark.django_db
class TestDistrictFetchGeoShapes:
    def test_saves_geometry(self, admin_client):
        district = DistrictFactory(code="WK051801")
        geometry = [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]
        with patch("scraping.admin.cbs.fetch_district_geometry", return_value=geometry):
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_geo_shapes", ACTION_CHECKBOX_NAME: [district.pk]},
            )
        district.refresh_from_db()
        assert district.geometry == geometry
        assert district.geometry_fetched_at is not None


@pytest.mark.django_db
class TestDistrictFetchStats:
    def test_saves_stats(self, admin_client):
        district = DistrictFactory(code="WK051801")
        with patch(
            "scraping.admin.cbs.fetch_district_stats",
            return_value=({"woz": 280}, 2024),
        ):
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_stats", ACTION_CHECKBOX_NAME: [district.pk]},
            )
        district.refresh_from_db()
        assert district.stats == {"woz": 280}
        assert district.stats_year == 2024
        assert district.stats_fetched_at is not None


@pytest.mark.django_db
class TestDistrictFetchNeighbourhoods:
    def test_creates_neighbourhoods(self, admin_client):
        district = DistrictFactory(code="WK051801")
        with patch(
            "scraping.admin.cbs.fetch_neighbourhoods_for_district",
            return_value=[
                {"code": "BU05180100", "name": "Schilderswijk-West"},
                {"code": "BU05180101", "name": "Schilderswijk-Oost"},
            ],
        ):
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_neighbourhoods", ACTION_CHECKBOX_NAME: [district.pk]},
            )
        assert Neighborhood.objects.filter(district=district).count() == 2
        nbh = Neighborhood.objects.get(code="BU05180100")
        assert nbh.name == "Schilderswijk-West"
        assert nbh.district == district
        assert nbh.city == district.city
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py::TestDistrictFetchGeoShapes tests/test_cbs_admin.py::TestDistrictFetchStats tests/test_cbs_admin.py::TestDistrictFetchNeighbourhoods -v
```

Expected: All 3 tests FAIL.

- [ ] **Step 3: Implement DistrictAdmin**

In `scraping/admin.py`, replace the existing `DistrictAdmin` class (lines 372–378) with:

```python
@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "has_geometry", "has_stats", "geometry_fetched_at", "stats_fetched_at")
    list_filter = ("city",)
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats", "fetch_neighbourhoods"]

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for district in queryset:
            try:
                district.geometry = cbs.fetch_district_geometry(district.code)
                district.geometry_fetched_at = now
                district.save(update_fields=["geometry", "geometry_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{district.code} ({exc})")
        self._report(request, "geo shapes", success, failures, "districts")

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for district in queryset:
            try:
                stats, year = cbs.fetch_district_stats(district.code)
                district.stats = stats
                district.stats_year = year
                district.stats_fetched_at = now
                district.save(update_fields=["stats", "stats_year", "stats_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{district.code} ({exc})")
        self._report(request, "stats", success, failures, "districts")

    @admin.action(description="Fetch neighbourhoods")
    def fetch_neighbourhoods(self, request, queryset):
        success, failures = 0, []
        for district in queryset:
            try:
                for n in cbs.fetch_neighbourhoods_for_district(district.code):
                    Neighborhood.objects.update_or_create(
                        code=n["code"],
                        defaults={"name": n["name"], "district": district, "city": district.city},
                    )
                success += 1
            except Exception as exc:
                failures.append(f"{district.code} ({exc})")
        self._report(request, "neighbourhoods", success, failures, "districts")

    @staticmethod
    def _report(request, entity, success, failures, level_name):
        msg = f"Fetched {entity} for {success} {level_name}."
        if failures:
            msg += f" Failed: {', '.join(failures)}."
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraping/admin.py tests/test_cbs_admin.py
git commit -m "$(cat <<'EOF'
Services|Add: CBS admin actions for District (geo shapes, stats, neighbourhoods)
EOF
)"
```

---

### Task 5: Admin Actions — NeighborhoodAdmin

**Files:**
- Modify: `tests/test_cbs_admin.py`
- Modify: `scraping/admin.py:381-387`

- [ ] **Step 1: Write tests for NeighborhoodAdmin actions**

Append to `tests/test_cbs_admin.py`:

```python
from tests.factories import NeighborhoodFactory


@pytest.mark.django_db
class TestNeighbourhoodFetchGeoShapes:
    def test_saves_geometry(self, admin_client):
        nbh = NeighborhoodFactory(code="BU05180100")
        geometry = [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]
        with patch("scraping.admin.cbs.fetch_neighbourhood_geometry", return_value=geometry):
            admin_client.post(
                "/admin/scraping/neighborhood/",
                {"action": "fetch_geo_shapes", ACTION_CHECKBOX_NAME: [nbh.pk]},
            )
        nbh.refresh_from_db()
        assert nbh.geometry == geometry
        assert nbh.geometry_fetched_at is not None


@pytest.mark.django_db
class TestNeighbourhoodFetchStats:
    def test_saves_stats(self, admin_client):
        nbh = NeighborhoodFactory(code="BU05180100")
        with patch(
            "scraping.admin.cbs.fetch_neighbourhood_stats",
            return_value=({"woz": 200}, 2024),
        ):
            admin_client.post(
                "/admin/scraping/neighborhood/",
                {"action": "fetch_stats", ACTION_CHECKBOX_NAME: [nbh.pk]},
            )
        nbh.refresh_from_db()
        assert nbh.stats == {"woz": 200}
        assert nbh.stats_year == 2024
        assert nbh.stats_fetched_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py::TestNeighbourhoodFetchGeoShapes tests/test_cbs_admin.py::TestNeighbourhoodFetchStats -v
```

Expected: Both tests FAIL.

- [ ] **Step 3: Implement NeighborhoodAdmin**

In `scraping/admin.py`, replace the existing `NeighborhoodAdmin` class (lines 381–387) with:

```python
@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "district", "has_geometry", "has_stats", "geometry_fetched_at", "stats_fetched_at")
    list_filter = ("city",)
    search_fields = ("code", "name")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")
    actions = ["fetch_geo_shapes", "fetch_stats"]

    @admin.action(description="Fetch geo shapes")
    def fetch_geo_shapes(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for nbh in queryset:
            try:
                nbh.geometry = cbs.fetch_neighbourhood_geometry(nbh.code)
                nbh.geometry_fetched_at = now
                nbh.save(update_fields=["geometry", "geometry_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{nbh.code} ({exc})")
        self._report(request, "geo shapes", success, failures, "neighbourhoods")

    @admin.action(description="Fetch stats")
    def fetch_stats(self, request, queryset):
        success, failures = 0, []
        now = timezone.now()
        for nbh in queryset:
            try:
                stats, year = cbs.fetch_neighbourhood_stats(nbh.code)
                nbh.stats = stats
                nbh.stats_year = year
                nbh.stats_fetched_at = now
                nbh.save(update_fields=["stats", "stats_year", "stats_fetched_at"])
                success += 1
            except Exception as exc:
                failures.append(f"{nbh.code} ({exc})")
        self._report(request, "stats", success, failures, "neighbourhoods")

    @staticmethod
    def _report(request, entity, success, failures, level_name):
        msg = f"Fetched {entity} for {success} {level_name}."
        if failures:
            msg += f" Failed: {', '.join(failures)}."
            messages.warning(request, msg)
        else:
            messages.success(request, msg)

    @admin.display(boolean=True, description="Geo")
    def has_geometry(self, obj):
        return obj.geometry is not None

    @admin.display(boolean=True, description="Stats")
    def has_stats(self, obj):
        return obj.stats is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd services/api && uv run pytest tests/test_cbs_admin.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraping/admin.py tests/test_cbs_admin.py
git commit -m "$(cat <<'EOF'
Services|Add: CBS admin actions for Neighbourhood (geo shapes, stats)
EOF
)"
```

---

### Task 6: Cleanup — Remove Old Code and Fix Broken Tests

**Files:**
- Modify: `scraping/tasks.py:1-17, 212-240`
- Delete: `tests/test_cbs_fetcher.py`
- Modify: `tests/factories.py`
- Modify: `tests/test_cities.py` (if needed)
- Modify: `tests/test_stats.py` (if needed)
- Modify: `tests/test_shapes.py` (if needed)

- [ ] **Step 1: Remove sync_cbs_data task**

In `scraping/tasks.py`:

Remove the CBS imports (lines 7–8):
```python
# Remove these lines:
from scraping.services.cbs import fetch_and_store_cities, fetch_and_store_districts
```

Remove the entire `sync_cbs_data` function (lines 212–240).

- [ ] **Step 2: Remove the `httpx` import from tasks.py if no longer needed**

Check if `httpx` is used elsewhere in `tasks.py`. If only used by CBS code, remove the `import httpx` line (line 2).

- [ ] **Step 3: Remove the `httpx` import from admin.py**

The existing `admin.py` has `import httpx` at line 1. Check if httpx is still used elsewhere in admin.py. If not (CBS now uses `cbs` module), remove it.

- [ ] **Step 4: Delete old test file**

```bash
rm services/api/tests/test_cbs_fetcher.py
```

- [ ] **Step 5: Update factories**

In `tests/factories.py`, the factories don't explicitly declare `fetched_at` — the models default to `None`. But verify the factories still work with the new field names. No changes should be needed since the factories don't set `fetched_at`.

- [ ] **Step 6: Check and fix existing endpoint tests**

Run each existing test file individually to find failures:

```bash
cd services/api && uv run pytest tests/test_cities.py tests/test_stats.py tests/test_shapes.py -v
```

These tests create model instances via factories and query the API. They shouldn't reference `fetched_at` directly, but check:
- If any test sets `fetched_at` on a factory instance, change to `geometry_fetched_at` or `stats_fetched_at` as appropriate.
- If any test asserts on `fetched_at` in response data, update accordingly.

The API schemas (`CityOut`, `CityStatsOut`, etc.) don't include `fetched_at`, so endpoint responses should be unaffected.

- [ ] **Step 7: Run the full test suite**

Run:
```bash
cd services/api && uv run pytest tests/ -v
```

Expected: All tests PASS. If any failures remain, fix them.

- [ ] **Step 8: Commit**

```bash
git add -u scraping/tasks.py scraping/admin.py tests/
git commit -m "$(cat <<'EOF'
Services|Remove: old sync_cbs_data task and CBS fetcher tests
EOF
)"
```

---

### Task 7: Full Verification

- [ ] **Step 1: Run complete test suite**

```bash
cd services/api && uv run pytest tests/ -v
```

Expected: All tests PASS, no failures, no warnings about deprecated fields.

- [ ] **Step 2: Run linting**

```bash
cd services/api && uv run ruff check . && uv run ruff format --check .
```

Expected: No linting or formatting errors. If ruff isn't the linter, use:

```bash
uv run yamllint . && uv run ansible-lint
```

(These are for the gitops repo; the Django project may use different linting — check `pyproject.toml` for the linting config.)

- [ ] **Step 3: Verify Django admin loads**

```bash
cd services/api && uv run python manage.py check
```

Expected: `System check identified no issues.`

- [ ] **Step 4: Verify migrations are complete**

```bash
cd services/api && uv run python manage.py showmigrations scraping | tail -5
```

Expected: All migrations are applied (marked with `[X]`).

- [ ] **Step 5: Spot-check the admin template renders**

```bash
cd services/api && uv run python -c "
from django.template.loader import get_template
t = get_template('admin/scraping/city/change_list.html')
print('Template found:', t.origin)
"
```

Expected: Prints the template path, confirming Django can find it.
