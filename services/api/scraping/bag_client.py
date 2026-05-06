from dataclasses import dataclass
from enum import StrEnum
from typing import Self

import httpx

# Kadaster Individuele Bevragingen v2. The acceptance environment is at
# api.bag.acceptatie.kadaster.nl — switch via base_url if you need to test
# against synthetic data without burning prod rate limit quota.
_BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"


class BagLookupFailure(StrEnum):
    MISSING_ADDRESS = "missing_address"
    NO_MATCH = "no_match"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class BagLookupSuccess:
    bag_id: str
    street: str
    house_number: int
    house_letter: str | None
    house_number_suffix: str | None
    postcode: str
    city: str


BagLookupResult = BagLookupSuccess | BagLookupFailure


class BagClient:
    """Resolves Dutch addresses to BAG records via Kadaster Individuele
    Bevragingen v2. Use as a context manager so the httpx client closes
    cleanly after each batch of lookups."""

    def __init__(self, *, api_key: str, base_url: str = _BAG_BASE_URL, timeout: float = 10.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "X-Api-Key": api_key,
                "Accept": "application/hal+json",
                "Accept-Crs": "epsg:28992",
            },
            timeout=timeout,
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._client.close()

    def lookup(
        self,
        *,
        postcode: str | None,
        house_number: int | None,
        house_letter: str | None = None,
        house_number_suffix: str | None = None,
    ) -> BagLookupResult:
        if not postcode or house_number is None:
            return BagLookupFailure.MISSING_ADDRESS

        params: dict[str, str | int] = {
            "postcode": postcode.replace(" ", "").upper(),
            "huisnummer": house_number,
        }
        if house_letter:
            params["huisletter"] = house_letter
        if house_number_suffix:
            params["huisnummertoevoeging"] = house_number_suffix

        response = self._client.get("/adressen", params=params)
        if response.status_code == 404:
            return BagLookupFailure.NO_MATCH
        response.raise_for_status()

        addresses = (response.json().get("_embedded") or {}).get("adressen") or []
        if not addresses:
            return BagLookupFailure.NO_MATCH
        if len(addresses) > 1:
            return BagLookupFailure.AMBIGUOUS

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
