from __future__ import annotations

import time
from datetime import datetime, timedelta

import httpx
from django.conf import settings
from django.utils import timezone
from loguru import logger

from scraping.models import City, District, Neighborhood

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


# ---------------------------------------------------------------------------
# Cache TTL
# ---------------------------------------------------------------------------


def is_stale(fetched_at) -> bool:
    if fetched_at is None:
        return True
    ttl = timedelta(days=settings.CBS_CACHE_TTL_DAYS)
    return timezone.now() - fetched_at > ttl


# ---------------------------------------------------------------------------
# WFS client
# ---------------------------------------------------------------------------


def _wfs_get(
    type_name: str,
    *,
    year: int = CBS_PRIMARY_YEAR,
    bbox: str | None = None,
    cql_filter: str | None = None,
    count: int = 4000,
    start_index: int = 0,
    max_retries: int = 6,
    initial_delay: float = 1.0,
) -> list[dict]:
    url = CBS_WFS_URL.format(year=year)
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": type_name,
        "outputFormat": "application/json",
        "srsName": "urn:ogc:def:crs:EPSG::4326",
        "count": count,
        "startIndex": start_index,
    }
    if bbox:
        params["bbox"] = bbox
    if cql_filter:
        params["CQL_FILTER"] = cql_filter

    delay = initial_delay
    last_error = ""
    for attempt in range(max_retries):
        try:
            response = httpx.get(url, params=params, timeout=180)
            if response.status_code == 200:
                return response.json().get("features", [])
            last_error = f"status={response.status_code}"
        except httpx.HTTPError as exc:
            last_error = str(exc)
        if attempt < max_retries - 1:
            time.sleep(delay)
            delay = min(delay * 2, 20)
    raise RuntimeError(f"CBS WFS request failed after {max_retries} attempts: {last_error}")


# ---------------------------------------------------------------------------
# Data transformation helpers
# ---------------------------------------------------------------------------


def _clean_stats(properties: dict) -> dict:
    cleaned = {}
    for key, value in properties.items():
        if isinstance(value, int | float) and (value in CBS_SENTINEL_VALUES or value <= -99990):
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def _extract_geometry(geom: dict) -> list:
    gtype = geom.get("type", "")
    coords = geom.get("coordinates", [])
    if gtype == "Polygon":
        polygons = [coords]
    elif gtype == "MultiPolygon":
        polygons = coords
    else:
        return []
    return [[_round_ring(ring) for ring in poly] for poly in polygons]


def _round_ring(ring: list) -> list:
    return [[round(x, 5), round(y, 5)] for x, y in ring]


def _bbox_for_city(city: City) -> str | None:
    if not city.geometry:
        return None
    min_lat, min_lon = float("inf"), float("inf")
    max_lat, max_lon = float("-inf"), float("-inf")
    for poly in city.geometry:
        for ring in poly:
            for lon, lat in ring:
                min_lat, min_lon = min(min_lat, lat), min(min_lon, lon)
                max_lat, max_lon = max(max_lat, lat), max(max_lon, lon)
    return f"{min_lat},{min_lon},{max_lat},{max_lon},urn:ogc:def:crs:EPSG::4326"


def _merge_backfill(primary_stats: dict, sec_index: dict[str, dict], code: str) -> dict:
    sec_props = sec_index.get(code, {})
    for field in BACKFILL_FIELDS:
        if primary_stats.get(field) is None and field in sec_props:
            backfill_val = sec_props[field]
            if isinstance(backfill_val, int | float) and (
                backfill_val in CBS_SENTINEL_VALUES or backfill_val <= -99990
            ):
                backfill_val = None
            primary_stats[field] = backfill_val
    return primary_stats


def _build_secondary_index(features: list[dict]) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for feat in features:
        props = feat.get("properties", {})
        code = props.get("wijkcode") or props.get("buurtcode") or ""
        if code:
            index[code] = _clean_stats(props)
    return index


# ---------------------------------------------------------------------------
# Per-entity processors
# ---------------------------------------------------------------------------


def _process_gemeente(
    props: dict, geom: dict | None, city: City, sec_index: dict[str, dict], now: datetime
) -> None:
    gm_code = f"GM{city.code}"
    stats = _merge_backfill(_clean_stats(props), sec_index, gm_code)
    update_fields = ["stats", "stats_year", "fetched_at", "updated_at"]
    city.stats = stats
    city.stats_year = CBS_PRIMARY_YEAR
    city.fetched_at = now
    if geom:
        city.geometry = _extract_geometry(geom)
        update_fields.append("geometry")
    city.save(update_fields=update_fields)


def _process_district(
    props: dict, geom: dict | None, city: City, sec_index: dict[str, dict], now: datetime
) -> District:
    wijk_code = props["wijkcode"]
    stats = _merge_backfill(_clean_stats(props), sec_index, wijk_code)
    geometry = _extract_geometry(geom) if geom else None
    district, _ = District.objects.update_or_create(
        code=wijk_code,
        defaults={
            "name": props.get("wijknaam", ""),
            "city": city,
            "geometry": geometry,
            "stats": stats,
            "stats_year": CBS_PRIMARY_YEAR,
            "fetched_at": now,
        },
    )
    return district


def _process_neighborhood(
    props: dict,
    geom: dict | None,
    city: City,
    districts_by_code: dict[str, District],
    sec_index: dict[str, dict],
    now: datetime,
) -> None:
    buurt_code = props["buurtcode"]
    stats = _merge_backfill(_clean_stats(props), sec_index, buurt_code)
    geometry = _extract_geometry(geom) if geom else None
    Neighborhood.objects.update_or_create(
        code=buurt_code,
        defaults={
            "name": props.get("buurtnaam", ""),
            "city": city,
            "district": districts_by_code.get(props.get("wijkcode", "")),
            "geometry": geometry,
            "stats": stats,
            "stats_year": CBS_PRIMARY_YEAR,
            "fetched_at": now,
        },
    )


# ---------------------------------------------------------------------------
# Feature classification and dispatch
# ---------------------------------------------------------------------------


def _classify_and_store_features(features: list[dict], city: City, sec_index: dict[str, dict]) -> None:
    wk_prefix = f"WK{city.code}"
    bu_prefix = f"BU{city.code}"
    gm_code = f"GM{city.code}"
    now = timezone.now()
    districts_by_code: dict[str, District] = {}

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry")

        if props.get("gemeentecode", "") == gm_code:
            _process_gemeente(props, geom, city, sec_index, now)
        elif props.get("buurtcode", "").startswith(bu_prefix):
            _process_neighborhood(props, geom, city, districts_by_code, sec_index, now)
        elif props.get("wijkcode", "").startswith(wk_prefix):
            district = _process_district(props, geom, city, sec_index, now)
            districts_by_code[district.code] = district


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


_CITIES_PAGE_SIZE = 50


def fetch_and_store_cities() -> None:
    logger.info("Fetching municipality list from CBS WFS")
    start_index = 0

    while True:
        features = _wfs_get(
            "wijkenbuurten:gemeenten", count=_CITIES_PAGE_SIZE, start_index=start_index
        )
        if not features:
            break

        for feat in features:
            props = feat.get("properties", {})
            raw_code = props.get("gemeentecode", "")
            code = raw_code.removeprefix("GM")
            if not code:
                continue
            City.objects.update_or_create(
                code=code,
                defaults={"name": props.get("gemeentenaam", "")},
            )

        start_index += len(features)
        if len(features) < _CITIES_PAGE_SIZE:
            break

    logger.info("Stored {} municipalities", City.objects.count())


def _ensure_city_geometry(city: City) -> None:
    if city.geometry:
        return
    gm_code = f"GM{city.code}"
    features = _wfs_get("wijkenbuurten:gemeenten", cql_filter=f"gemeentecode='{gm_code}'")
    if features:
        geom = features[0].get("geometry")
        if geom:
            city.geometry = _extract_geometry(geom)
            city.save(update_fields=["geometry", "updated_at"])


def fetch_and_store_districts(city: City) -> None:
    logger.info("Fetching districts and neighborhoods for {} ({})", city.name, city.code)
    _ensure_city_geometry(city)
    bbox = _bbox_for_city(city)

    primary_features = _wfs_get(
        "wijkenbuurten:gemeenten,wijkenbuurten:wijken,wijkenbuurten:buurten",
        year=CBS_PRIMARY_YEAR,
        bbox=bbox,
    )
    secondary_features = _wfs_get(
        "wijkenbuurten:wijken,wijkenbuurten:buurten",
        year=CBS_SECONDARY_YEAR,
        bbox=bbox,
    )

    sec_index = _build_secondary_index(secondary_features)
    _classify_and_store_features(primary_features, city, sec_index)

    logger.info(
        "Stored {} districts, {} neighborhoods for {}",
        District.objects.filter(city=city).count(),
        Neighborhood.objects.filter(city=city).count(),
        city.name,
    )
