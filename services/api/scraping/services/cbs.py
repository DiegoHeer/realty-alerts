from __future__ import annotations

import httpx

CBS_ODATA_BASE = "https://opendata.cbs.nl/ODataApi/odata/85618NED"
CBS_ODATA_YEAR = 2023
_PDOK_COLLECTIONS_URL = "https://api.pdok.nl/cbs/gebiedsindelingen/ogc/v1/collections"
_ODATA_METADATA_KEYS = frozenset(
    {
        "ID",
        "WijkenEnBuurten",
        "Gemeentenaam_1",
        "SoortRegio_2",
        "Codering_3",
        "IndelingswijzigingGemeenteWijkBuurt_4",
    }
)


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


def _odata_get(table: str, *, filter: str, select: str | None = None, top: int = 500) -> list[dict]:
    url = f"{CBS_ODATA_BASE}/{table}"
    params: dict[str, str | int] = {"$filter": filter, "$top": top}
    if select:
        params["$select"] = select
    resp = httpx.get(url, params=params, timeout=30.0)
    resp.raise_for_status()
    return resp.json().get("value", [])


def _pdok_collection_url(collection: str) -> str:
    return f"{_PDOK_COLLECTIONS_URL}/{collection}/items"


def _pdok_ogc_all_features(
    collection: str,
    *,
    jaarcode: int = CBS_ODATA_YEAR,
    bbox: tuple[float, float, float, float] | None = None,
) -> list[dict]:
    url = _pdok_collection_url(collection)
    all_features: list[dict] = []
    params: dict[str, str | int] = {"f": "json", "jaarcode": jaarcode, "limit": 1000}
    if bbox:
        params["bbox"] = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    while True:
        resp = httpx.get(url, params=params, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        all_features.extend(data.get("features", []))
        next_url = None
        for link in data.get("links", []):
            if link.get("rel") == "next":
                next_url = link["href"]
                break
        if not next_url:
            break
        url = next_url
        params = {}
    return all_features


def _bbox_from_geometries(geometries: list[list]) -> tuple[float, float, float, float] | None:
    min_lon, min_lat = float("inf"), float("inf")
    max_lon, max_lat = float("-inf"), float("-inf")
    found = False
    for multi_polygon in geometries:
        for polygon in multi_polygon:
            for ring in polygon:
                for lon, lat in ring:
                    min_lon, min_lat = min(min_lon, lon), min(min_lat, lat)
                    max_lon, max_lat = max(max_lon, lon), max(max_lat, lat)
                    found = True
    if not found:
        return None
    return (min_lon, min_lat, max_lon, max_lat)


def _strip_stats(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in _ODATA_METADATA_KEYS}


# --- Hierarchy functions ---


def fetch_all_cities() -> list[dict]:
    url = _pdok_collection_url("gemeente_gegeneraliseerd")
    resp = httpx.get(
        url,
        params={"limit": 500, "f": "json", "jaarcode": CBS_ODATA_YEAR},
        timeout=30.0,
    )
    resp.raise_for_status()
    return [
        {
            "code": f["properties"]["statcode"].removeprefix("GM"),
            "name": f["properties"]["statnaam"],
        }
        for f in resp.json()["features"]
    ]


def fetch_districts_for_city(city_code: str) -> list[dict]:
    rows = _odata_get(
        "WijkenEnBuurten",
        filter=f"substringof('WK{city_code}',Key)",
        select="Key,Title",
    )
    return [
        {"code": r["Key"].strip(), "name": r["Title"].strip()}
        for r in rows
        if r["Key"].strip().startswith(f"WK{city_code}")
    ]


def fetch_neighbourhoods_for_district(district_code: str) -> list[dict]:
    buurt_prefix = f"BU{district_code[2:]}"
    rows = _odata_get(
        "WijkenEnBuurten",
        filter=f"substringof('{buurt_prefix}',Key)",
        select="Key,Title",
    )
    return [
        {"code": r["Key"].strip(), "name": r["Title"].strip()}
        for r in rows
        if r["Key"].strip().startswith(buurt_prefix)
    ]


# --- Geometry functions ---


def fetch_city_geometry(codes: list[str]) -> dict[str, list]:
    url = _pdok_collection_url("gemeente_gegeneraliseerd")
    resp = httpx.get(
        url,
        params={"limit": 500, "f": "json", "jaarcode": CBS_ODATA_YEAR},
        timeout=30.0,
    )
    resp.raise_for_status()
    wanted = set(codes)
    result: dict[str, list] = {}
    for feature in resp.json()["features"]:
        code = feature["properties"]["statcode"].removeprefix("GM")
        if code in wanted:
            result[code] = _extract_geometry(feature["geometry"])
    return result


def fetch_district_geometry(
    codes: list[str],
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, list]:
    features = _pdok_ogc_all_features("wijk_gegeneraliseerd", bbox=bbox)
    wanted = set(codes)
    result: dict[str, list] = {}
    for f in features:
        code = f["properties"]["statcode"].strip()
        if code in wanted:
            result[code] = _extract_geometry(f["geometry"])
    return result


def fetch_neighbourhood_geometry(
    codes: list[str],
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, list]:
    features = _pdok_ogc_all_features("buurt_gegeneraliseerd", bbox=bbox)
    wanted = set(codes)
    result: dict[str, list] = {}
    for f in features:
        code = f["properties"]["statcode"].strip()
        if code in wanted:
            result[code] = _extract_geometry(f["geometry"])
    return result


def fetch_entity_geometry(
    collection: str,
    code: str,
    *,
    bbox: tuple[float, float, float, float] | None = None,
) -> list | None:
    features = _pdok_ogc_all_features(collection, bbox=bbox)
    for f in features:
        if f["properties"]["statcode"].strip() == code:
            return _extract_geometry(f["geometry"])
    return None


# --- Stats functions ---


def fetch_city_stats(codes: list[str]) -> dict[str, dict]:
    odata_filter = " or ".join(f"WijkenEnBuurten eq '{f'GM{c}'.ljust(10)}'" for c in codes)
    rows = _odata_get("TypedDataSet", filter=odata_filter, top=len(codes))
    return {r["Codering_3"].strip(): _strip_stats(r) for r in rows}


def fetch_district_stats(codes: list[str]) -> dict[str, dict]:
    odata_filter = " or ".join(f"WijkenEnBuurten eq '{c.ljust(10)}'" for c in codes)
    rows = _odata_get("TypedDataSet", filter=odata_filter, top=len(codes))
    return {r["Codering_3"].strip(): _strip_stats(r) for r in rows}


def fetch_neighbourhood_stats(codes: list[str]) -> dict[str, dict]:
    odata_filter = " or ".join(f"WijkenEnBuurten eq '{c.ljust(10)}'" for c in codes)
    rows = _odata_get("TypedDataSet", filter=odata_filter, top=len(codes))
    return {r["Codering_3"].strip(): _strip_stats(r) for r in rows}


def fetch_entity_stats(odata_key: str) -> dict | None:
    rows = _odata_get(
        "TypedDataSet",
        filter=f"WijkenEnBuurten eq '{odata_key.ljust(10)}'",
        top=1,
    )
    if not rows:
        return None
    return _strip_stats(rows[0])
