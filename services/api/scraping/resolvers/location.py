import re
from dataclasses import dataclass

import httpx
from loguru import logger

_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_WKT_POINT_RE = re.compile(r"^POINT\(([^ ]+) ([^ ]+)\)$")
_LOCATION_FIELDS = "centroide_ll,buurtnaam,wijknaam,buurtcode"


@dataclass(frozen=True, slots=True)
class PdokLocationResult:
    latitude: float
    longitude: float
    neighbourhood: str | None = None
    district: str | None = None
    neighbourhood_code: str | None = None


class PdokLocationLookup:
    def __init__(self, client: httpx.Client | None = None, base_url: str = _PDOK_BASE_URL) -> None:
        self._client = client or httpx.Client(base_url=base_url, timeout=5.0)
        self._owns_client = client is None

    def __enter__(self) -> PdokLocationLookup:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def lookup(self, bag_id: str) -> PdokLocationResult | None:
        try:
            response = self._client.get(
                "/free",
                params={"q": f"nummeraanduiding_id:{bag_id}", "fl": _LOCATION_FIELDS, "rows": 1},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PDOK location lookup failed for {}: {}", bag_id, exc)
            return None

        docs = response.json().get("response", {}).get("docs", [])
        if not docs:
            logger.warning("PDOK returned no results for bag_id {}", bag_id)
            return None

        doc = docs[0]
        wkt = doc.get("centroide_ll", "")
        match = _WKT_POINT_RE.match(wkt)
        if not match:
            logger.warning("PDOK returned unparseable WKT for bag_id {}: {}", bag_id, wkt)
            return None

        lon, lat = float(match.group(1)), float(match.group(2))
        return PdokLocationResult(
            latitude=lat,
            longitude=lon,
            neighbourhood=doc.get("buurtnaam"),
            district=doc.get("wijknaam"),
            neighbourhood_code=doc.get("buurtcode"),
        )
