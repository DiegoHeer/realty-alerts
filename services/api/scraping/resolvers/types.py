from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


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


@dataclass(frozen=True)
class AddressQuery:
    postcode: str | None
    house_number: int | None
    house_letter: str | None = None
    house_number_suffix: str | None = None
    street: str | None = None
    city: str | None = None

    def without_specifics(self) -> "AddressQuery":
        return AddressQuery(
            postcode=self.postcode,
            house_number=self.house_number,
            street=self.street,
            city=self.city,
        )


class AddressResolver(Protocol):
    def resolve(self, query: AddressQuery) -> BagLookupResult | None: ...
