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


def _pdok_ogc_all_features(collection: str, *, jaarcode: int = CBS_ODATA_YEAR) -> list[dict]:
    url = _pdok_collection_url(collection)
    all_features: list[dict] = []
    params: dict[str, str | int] = {"f": "json", "jaarcode": jaarcode, "limit": 1000}
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


def fetch_city_geometry(city_code: str) -> list:
    url = _pdok_collection_url("gemeente_gegeneraliseerd")
    resp = httpx.get(
        url,
        params={"limit": 500, "f": "json", "jaarcode": CBS_ODATA_YEAR},
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
    features = _pdok_ogc_all_features("wijk_gegeneraliseerd")
    for f in features:
        if f["properties"]["statcode"].strip() == district_code:
            return _extract_geometry(f["geometry"])
    msg = f"District {district_code} not found"
    raise ValueError(msg)


def fetch_neighbourhood_geometry(neighbourhood_code: str) -> list:
    features = _pdok_ogc_all_features("buurt_gegeneraliseerd")
    for f in features:
        if f["properties"]["statcode"].strip() == neighbourhood_code:
            return _extract_geometry(f["geometry"])
    msg = f"Neighbourhood {neighbourhood_code} not found"
    raise ValueError(msg)


# --- Stats functions ---


def _odata_stats(code: str, entity_label: str) -> tuple[dict, int]:
    padded = code.ljust(10)
    rows = _odata_get("TypedDataSet", filter=f"WijkenEnBuurten eq '{padded}'")
    if not rows:
        msg = f"No stats found for {entity_label}"
        raise ValueError(msg)
    return {k: v for k, v in rows[0].items() if k not in _ODATA_METADATA_KEYS}, CBS_ODATA_YEAR


def fetch_city_stats(city_code: str) -> tuple[dict, int]:
    return _odata_stats(f"GM{city_code}", f"city {city_code}")


def fetch_district_stats(district_code: str) -> tuple[dict, int]:
    return _odata_stats(district_code, f"district {district_code}")


def fetch_neighbourhood_stats(neighbourhood_code: str) -> tuple[dict, int]:
    return _odata_stats(neighbourhood_code, f"neighbourhood {neighbourhood_code}")
