from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

_ARCGIS_BASE_URL = "https://gis.gdngeoservices.nl/standalone/rest/services/blk_gdn/lks_blk_rd_v1/MapServer/0/query"

_STATUS_SEVERITY = {
    "onverdacht/niet verontreinigd": 0,
    "niet ernstig, niet verontreinigd": 0,
    "niet ernstig, licht tot matig verontreinigd": 1,
    "niet ernstig, verontreinigd": 1,
    "potentieel ernstig": 2,
    "ernstig, geen risico's bepaald": 3,
    "ernstig, risico's bepaald": 4,
}


def _status_severity(status: str) -> int:
    return _STATUS_SEVERITY.get(status.lower().strip(), 2)


@dataclass(frozen=True, slots=True)
class BodemloketResult:
    investigation_count: int
    contamination_status: str | None = None
    investigation_outcome: str | None = None


class BodemloketLookup:
    def __init__(self, client: httpx.Client | None = None, base_url: str = _ARCGIS_BASE_URL) -> None:
        self._base_url = base_url
        self._client = client or httpx.Client(timeout=10.0)
        self._owns_client = client is None

    def __enter__(self) -> BodemloketLookup:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def lookup(self, latitude: float, longitude: float) -> BodemloketResult | None:
        params = {
            "geometryType": "esriGeometryPoint",
            "geometry": f"{longitude},{latitude}",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": "STATUS_OORD,VERVOLG_WBB",
            "returnGeometry": "false",
            "f": "json",
        }
        try:
            response = self._client.get(self._base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Bodemloket lookup failed for ({}, {}): {}", latitude, longitude, exc)
            return None

        features = response.json().get("features", [])
        if not features:
            return BodemloketResult(investigation_count=0)

        worst = max(features, key=lambda f: _status_severity(f.get("attributes", {}).get("STATUS_OORD", "")))
        attrs = worst.get("attributes", {})

        return BodemloketResult(
            investigation_count=len(features),
            contamination_status=attrs.get("STATUS_OORD"),
            investigation_outcome=attrs.get("VERVOLG_WBB"),
        )
