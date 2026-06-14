from __future__ import annotations

import time
from datetime import timedelta

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


def is_stale(fetched_at) -> bool:
    if fetched_at is None:
        return True
    ttl = timedelta(days=settings.CBS_CACHE_TTL_DAYS)
    return timezone.now() - fetched_at > ttl


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


def _wfs_get(
    type_name: str,
    *,
    year: int = CBS_PRIMARY_YEAR,
    bbox: str | None = None,
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
        "count": 4000,
    }
    if bbox:
        params["bbox"] = bbox

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


def fetch_and_store_cities() -> None:
    logger.info("Fetching municipality list from CBS WFS")
    features = _wfs_get("wijkenbuurten:gemeenten")

    for feat in features:
        props = feat.get("properties", {})
        raw_code = props.get("gemeentecode", "")
        code = raw_code.removeprefix("GM")
        if not code:
            continue
        name = props.get("gemeentenaam", "")
        geom = feat.get("geometry")
        geometry = _extract_geometry(geom) if geom else None

        City.objects.update_or_create(
            code=code,
            defaults={"name": name, "geometry": geometry},
        )

    logger.info("Stored {} municipalities", City.objects.count())


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


def _merge_backfill(primary_stats: dict, secondary_features: dict[str, dict], code: str) -> dict:
    sec_props = secondary_features.get(code, {})
    for field in BACKFILL_FIELDS:
        if primary_stats.get(field) is None and field in sec_props:
            backfill_val = sec_props[field]
            if isinstance(backfill_val, int | float) and (
                backfill_val in CBS_SENTINEL_VALUES or backfill_val <= -99990
            ):
                backfill_val = None
            primary_stats[field] = backfill_val
    return primary_stats


def fetch_and_store_districts(city: City) -> None:
    logger.info("Fetching districts and neighborhoods for {} ({})", city.name, city.code)
    bbox = _bbox_for_city(city)

    wk_prefix = f"WK{city.code}"
    bu_prefix = f"BU{city.code}"
    gm_code = f"GM{city.code}"

    primary_features = _wfs_get(
        "wijkenbuurten:gemeenten,wijkenbuurten:wijken,wijkenbuurten:buurten",
        year=CBS_PRIMARY_YEAR,
        bbox=bbox,
    )
    secondary_features_raw = _wfs_get(
        "wijkenbuurten:wijken,wijkenbuurten:buurten",
        year=CBS_SECONDARY_YEAR,
        bbox=bbox,
    )

    sec_by_code: dict[str, dict] = {}
    for feat in secondary_features_raw:
        props = feat.get("properties", {})
        code = props.get("wijkcode") or props.get("buurtcode") or ""
        if code:
            sec_by_code[code] = _clean_stats(props)

    now = timezone.now()
    districts_by_code: dict[str, District] = {}

    for feat in primary_features:
        props = feat.get("properties", {})
        geom = feat.get("geometry")

        gemeente_code = props.get("gemeentecode", "")
        if gemeente_code == gm_code:
            stats = _clean_stats(props)
            stats = _merge_backfill(stats, sec_by_code, gm_code)
            city.stats = stats
            city.stats_year = CBS_PRIMARY_YEAR
            city.fetched_at = now
            city.save(update_fields=["stats", "stats_year", "fetched_at", "updated_at"])
            continue

        buurt_code = props.get("buurtcode", "")
        if buurt_code.startswith(bu_prefix):
            stats = _clean_stats(props)
            stats = _merge_backfill(stats, sec_by_code, buurt_code)
            geometry = _extract_geometry(geom) if geom else None
            parent_wijk = props.get("wijkcode", "")
            district = districts_by_code.get(parent_wijk)
            Neighborhood.objects.update_or_create(
                code=buurt_code,
                defaults={
                    "name": props.get("buurtnaam", ""),
                    "city": city,
                    "district": district,
                    "geometry": geometry,
                    "stats": stats,
                    "stats_year": CBS_PRIMARY_YEAR,
                    "fetched_at": now,
                },
            )
            continue

        wijk_code = props.get("wijkcode", "")
        if wijk_code.startswith(wk_prefix):
            stats = _clean_stats(props)
            stats = _merge_backfill(stats, sec_by_code, wijk_code)
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
            districts_by_code[wijk_code] = district

    logger.info(
        "Stored {} districts, {} neighborhoods for {}",
        District.objects.filter(city=city).count(),
        Neighborhood.objects.filter(city=city).count(),
        city.name,
    )
