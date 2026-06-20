from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

_WFS_BASE_URL = "https://service.pdok.nl/rvo/indgebfunderingsproblematiek/wfs/v1_0"
_BBOX_DELTA = 0.0001


@dataclass(frozen=True, slots=True)
class FoundationRiskResult:
    label: str | None


class PdokFoundationRiskLookup:
    def __init__(self, client: httpx.Client | None = None, base_url: str = _WFS_BASE_URL) -> None:
        self._base_url = base_url
        self._client = client or httpx.Client(timeout=10.0)
        self._owns_client = client is None

    def __enter__(self) -> PdokFoundationRiskLookup:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def lookup(self, latitude: float, longitude: float) -> FoundationRiskResult | None:
        bbox = (
            f"{longitude - _BBOX_DELTA},{latitude - _BBOX_DELTA},"
            f"{longitude + _BBOX_DELTA},{latitude + _BBOX_DELTA},"
            f"urn:ogc:def:crs:EPSG::4326"
        )
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": "indgebfunderingsproblematiek:indgebfunderingsproblematiek",
            "outputFormat": "application/json",
            "count": 1,
            "BBOX": bbox,
        }
        try:
            response = self._client.get(self._base_url, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PDOK foundation risk lookup failed for ({}, {}): {}", latitude, longitude, exc)
            return None

        features = response.json().get("features", [])
        if not features:
            return FoundationRiskResult(label=None)

        label = features[0].get("properties", {}).get("legenda")
        if not label:
            logger.warning("PDOK foundation risk: missing legenda for ({}, {})", latitude, longitude)
            return FoundationRiskResult(label=None)

        return FoundationRiskResult(label=label)
