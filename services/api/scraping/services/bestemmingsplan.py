from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

_API_BASE_URL = "https://ruimte.omgevingswet.overheid.nl/ruimtelijke-plannen/api/opvragen/v4"


@dataclass(frozen=True, slots=True)
class BestemmingsplanResult:
    designation: str | None


class BestemmingsplanLookup:
    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        base_url: str = _API_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(base_url=base_url, timeout=15.0)
        self._owns_client = client is None

    def __enter__(self) -> BestemmingsplanLookup:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "Content-Type": "application/json",
            "Content-Crs": "epsg:4326",
            "Accept-Crs": "epsg:4326",
        }

    def _geo_body(self, latitude: float, longitude: float) -> dict:
        return {
            "_geo": {
                "intersects": {
                    "type": "Point",
                    "coordinates": [longitude, latitude],
                }
            }
        }

    def lookup(self, latitude: float, longitude: float) -> BestemmingsplanResult | None:
        try:
            response = self._client.post(
                "/plannen/_zoek",
                params={"planType": "bestemmingsplan", "regelStatus": "geldend"},
                headers=self._headers(),
                json=self._geo_body(latitude, longitude),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Bestemmingsplan plan lookup failed for ({}, {}): {}", latitude, longitude, exc)
            return None

        plannen = response.json().get("_embedded", {}).get("plannen", [])
        if not plannen:
            return BestemmingsplanResult(designation=None)

        return self._find_designation(plannen[0]["id"], latitude, longitude)

    def _find_designation(self, plan_id: str, latitude: float, longitude: float) -> BestemmingsplanResult | None:
        try:
            response = self._client.post(
                f"/plannen/{plan_id}/bestemmingsvlakken/_zoek",
                headers=self._headers(),
                json=self._geo_body(latitude, longitude),
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Bestemmingsplan vlakken lookup failed for plan {}: {}", plan_id, exc)
            return None

        vlakken = response.json().get("_embedded", {}).get("bestemmingsvlakken", [])
        if not vlakken:
            return BestemmingsplanResult(designation=None)

        hoofdgroep = vlakken[0].get("bestemmingshoofdgroep")
        if not hoofdgroep:
            return BestemmingsplanResult(designation=None)

        return BestemmingsplanResult(designation=hoofdgroep)
