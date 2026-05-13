from __future__ import annotations

from dataclasses import dataclass

import httpx

from scraping.resolvers.types import AddressQuery, BagLookupFailure, BagLookupResult, BagLookupSuccess

BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"


@dataclass(frozen=True)
class KadasterConfig:
    api_key: str
    base_url: str = BAG_BASE_URL
    timeout: float = 10.0


def _make_kadaster_client(config: KadasterConfig) -> httpx.Client:
    return httpx.Client(
        base_url=config.base_url,
        headers={
            "X-Api-Key": config.api_key,
            "Accept": "application/hal+json",
            "Accept-Crs": "epsg:28992",
        },
        timeout=config.timeout,
    )


def resolve_addresses(
    addresses: list[dict],
    *,
    house_letter: str | None,
    house_number_suffix: str | None,
) -> BagLookupSuccess | BagLookupFailure:
    if len(addresses) > 1:
        matches = [
            a
            for a in addresses
            if a.get("huisletter") == house_letter and a.get("huisnummertoevoeging") == house_number_suffix
        ]
        if len(matches) != 1:
            return BagLookupFailure.AMBIGUOUS
        addresses = matches
    address = addresses[0]
    return BagLookupSuccess(
        bag_id=address["nummeraanduidingIdentificatie"],
        street=address["openbareRuimteNaam"],
        house_number=int(address["huisnummer"]),
        house_letter=address.get("huisletter"),
        house_number_suffix=address.get("huisnummertoevoeging"),
        postcode=address["postcode"],
        city=address["woonplaatsNaam"],
    )


class KadasterPostcodeResolver:
    def __init__(self, config: KadasterConfig) -> None:
        self._client = _make_kadaster_client(config)

    def __enter__(self) -> KadasterPostcodeResolver:
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        if not query.postcode or query.house_number is None:
            return None

        params: dict[str, str | int] = {
            "postcode": query.postcode.replace(" ", "").upper(),
            "huisnummer": query.house_number,
        }
        if query.house_letter:
            params["huisletter"] = query.house_letter
        if query.house_number_suffix:
            params["huisnummertoevoeging"] = query.house_number_suffix

        response = self._client.get("/adressen", params=params)
        if response.is_client_error:
            return None
        response.raise_for_status()

        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return None
        return resolve_addresses(
            addresses, house_letter=query.house_letter, house_number_suffix=query.house_number_suffix
        )


class KadasterStreetCityResolver:
    def __init__(self, config: KadasterConfig) -> None:
        self._client = _make_kadaster_client(config)

    def __enter__(self) -> KadasterStreetCityResolver:
        return self

    def __exit__(self, *_) -> None:
        self._client.close()

    def close(self) -> None:
        self._client.close()

    def resolve(self, query: AddressQuery) -> BagLookupResult | None:
        if not query.street or not query.city or query.house_number is None:
            return None

        params: dict[str, str | int] = {
            "openbareRuimteNaam": query.street,
            "woonplaatsNaam": query.city,
            "huisnummer": query.house_number,
        }
        if query.house_letter:
            params["huisletter"] = query.house_letter
        if query.house_number_suffix:
            params["huisnummertoevoeging"] = query.house_number_suffix

        response = self._client.get("/adressen", params=params)
        if response.is_client_error:
            return None
        response.raise_for_status()

        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return None
        return resolve_addresses(
            addresses, house_letter=query.house_letter, house_number_suffix=query.house_number_suffix
        )
