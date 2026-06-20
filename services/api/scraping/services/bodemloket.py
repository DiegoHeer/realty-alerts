from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

_ARCGIS_BASE_URL = "https://www.gdngeoservices.nl/arcgis/rest/services/blk/lks_blk_rd/MapServer/1/query"


@dataclass(frozen=True, slots=True)
class BodemloketResult:
    wbb_count: int


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
            "returnCountOnly": "true",
            "f": "json",
        }
        try:
            response = self._client.get(self._base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Bodemloket lookup failed for ({}, {}): {}", latitude, longitude, exc)
            return None

        data = response.json()
        count = data.get("count")
        if count is not None:
            return BodemloketResult(wbb_count=count)

        features = data.get("features", [])
        return BodemloketResult(wbb_count=len(features))
