from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import httpx
from loguru import logger

from scraping.models import BuildingType, EnergyLabel

_EP_ONLINE_BASE_URL = "https://public.ep-online.nl/api/v5"

_BUILDING_TYPE_MAP: dict[str, BuildingType] = {
    "appartement": BuildingType.APARTMENT,
    "rijwoning tussen": BuildingType.TERRACED,
    "tussenwoning": BuildingType.TERRACED,
    "hoekwoning": BuildingType.CORNER,
    "twee onder één kap": BuildingType.SEMI_DETACHED,
    "twee-onder-één-kap": BuildingType.SEMI_DETACHED,
    "twee onder een kap": BuildingType.SEMI_DETACHED,
    "vrijstaand": BuildingType.DETACHED,
    "vrijstaande woning": BuildingType.DETACHED,
}

_ENERGY_LABEL_MAP: dict[str, EnergyLabel] = {str(label.value): label for label in EnergyLabel}


@dataclass(frozen=True, slots=True)
class EpOnlineBuildingDetails:
    building_type: BuildingType | None = None
    energy_label: EnergyLabel | None = None
    energy_label_valid_until: date | None = None


def _parse_building_type(raw: str | None) -> BuildingType | None:
    if not raw:
        return None
    result = _BUILDING_TYPE_MAP.get(raw.strip().lower())
    if result is None:
        logger.warning("Unknown EP-Online building type: {!r}", raw)
    return result


def _parse_energy_label(raw: str | None) -> EnergyLabel | None:
    if not raw:
        return None
    result = _ENERGY_LABEL_MAP.get(raw.strip())
    if result is None:
        logger.warning("Unknown EP-Online energy label: {!r}", raw)
    return result


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.split("T")[0])
    except ValueError:
        logger.warning("Unparseable EP-Online date: {!r}", raw)
        return None


class EpOnlineLookup:
    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        base_url: str = _EP_ONLINE_BASE_URL,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(base_url=base_url, timeout=10.0)
        self._owns_client = client is None

    def __enter__(self) -> EpOnlineLookup:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def lookup(
        self,
        postcode: str,
        house_number: int,
        house_letter: str | None = None,
        house_number_suffix: str | None = None,
    ) -> EpOnlineBuildingDetails | None:
        params: dict[str, str | int] = {"postcode": postcode, "huisnummer": house_number}
        if house_letter:
            params["huisletter"] = house_letter
        if house_number_suffix:
            params["huisnummertoevoeging"] = house_number_suffix

        try:
            response = self._client.get(
                "/PandEnergielabel/Adres",
                params=params,
                headers={"Authorization": self._api_key},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("EP-Online lookup failed for {} {}: {}", postcode, house_number, exc)
            return None

        records = response.json()
        if not records:
            return None

        record = records[0]
        return EpOnlineBuildingDetails(
            building_type=_parse_building_type(record.get("Gebouwtype")),
            energy_label=_parse_energy_label(record.get("Energieklasse")),
            energy_label_valid_until=_parse_date(record.get("Geldig_tot")),
        )
