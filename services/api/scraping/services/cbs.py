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
