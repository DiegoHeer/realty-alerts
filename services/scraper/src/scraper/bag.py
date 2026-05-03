from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self, cast

import polars as pl
from loguru import logger

from scraper.models import Listing


class BagMissReason(StrEnum):
    """Why the BAG matcher couldn't return a single row. Mirrors the API's
    `DeadListingReason` for the reasons the matcher itself emits — input
    quality reasons (parse failure, missing postcode AND street) are
    classified upstream by the runner."""

    MISSING_HOUSE_NUMBER = "missing_house_number"
    NO_MATCH = "bag_no_match"
    AMBIGUOUS = "bag_ambiguous"


BAG_DATA_PATH = Path(__file__).resolve().parent / "data" / "bag_addresses.parquet"


# Map of common colloquial Dutch city names to BAG's canonical woonplaats.
# Pararius/Funda surface "Den Haag" / "Den Bosch" while BAG stores the older
# 's-X form. Keys are lowercased for case-insensitive lookup.
_CITY_ALIASES: dict[str, str] = {
    "den haag": "'s-Gravenhage",
    "den bosch": "'s-Hertogenbosch",
}


def _normalise_postcode(postcode: str) -> str:
    return postcode.upper().replace(" ", "")


def _canonicalise_city(city: str) -> str:
    return _CITY_ALIASES.get(city.lower(), city)


def _format_address(
    *,
    postcode: str | None,
    street: str | None,
    house_number: int,
    house_letter: str | None,
    house_number_suffix: str | None,
    city: str | None,
) -> str:
    parts = [str(house_number)]
    if house_letter:
        parts.append(house_letter)
    if house_number_suffix:
        parts.append(house_number_suffix)
    number = "-".join(parts)
    return f"{postcode or '-'} {street or '-'} {number} {city or '-'}"


@dataclass(frozen=True, slots=True)
class BagMatch:
    bag_id: str
    postcode: str | None
    street: str | None
    house_number: int
    house_letter: str | None
    house_number_suffix: str | None
    city: str | None


class ParquetBagLookup:
    """BAG lookup backed by a local parquet snapshot."""

    def __init__(self, parquet_path: Path = BAG_DATA_PATH) -> None:
        self._path = parquet_path
        self._df: pl.LazyFrame | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._df = None

    def lookup(
        self,
        *,
        street: str | None,
        house_number: int | None,
        house_letter: str | None,
        house_number_suffix: str | None,
        postcode: str | None,
        city: str,
    ) -> BagMatch | BagMissReason:
        if house_number is None:
            return BagMissReason.MISSING_HOUSE_NUMBER

        address = _format_address(
            postcode=postcode,
            street=street,
            house_number=house_number,
            house_letter=house_letter,
            house_number_suffix=house_number_suffix,
            city=city,
        )
        candidates = self._find_candidates(street, house_number, postcode, city)
        if candidates.height == 0:
            logger.warning(f"No BAG match for {address}")
            return BagMissReason.NO_MATCH
        if candidates.height == 1:
            return self._to_match(candidates)
        return self._disambiguate(candidates, house_letter, house_number_suffix, city, address)

    def _disambiguate(
        self,
        candidates: pl.DataFrame,
        house_letter: str | None,
        house_number_suffix: str | None,
        city: str,
        address: str,
    ) -> BagMatch | BagMissReason:
        exact = self._filter_exact_pair(candidates, house_letter, house_number_suffix)
        if exact.height == 1:
            return self._to_match(exact)

        if exact.height == 0 and house_number_suffix and house_number_suffix.isdigit():
            by_digits = self._filter_by_toevoeging_digits(candidates, house_letter, house_number_suffix)
            if by_digits.height == 1:
                return self._to_match(by_digits)

        by_city = self._filter_by_city(candidates, city)
        if by_city.height == 1:
            return self._to_match(by_city)

        main = self._filter_main_address(candidates)
        if main.height == 1:
            logger.info(f"BAG fallback to building-level match for {address}")
            return self._to_match(main)

        logger.warning(f"Ambiguous BAG match for {address}: {candidates.height} candidates")
        return BagMissReason.AMBIGUOUS

    def _df_loaded(self) -> pl.LazyFrame:
        if self._df is None:
            logger.info(f"Lazy-scanning BAG parquet from {self._path}")
            self._df = pl.scan_parquet(self._path)
        return self._df

    def _find_candidates(
        self,
        street: str | None,
        house_number: int,
        postcode: str | None,
        city: str,
    ) -> pl.DataFrame:
        df = self._df_loaded()
        if not postcode:
            return self._collect_by_street_number_city(df, street, house_number, city)
        collected = cast(
            pl.DataFrame,
            df.filter(
                (pl.col("postcode") == _normalise_postcode(postcode)) & (pl.col("huisnummer") == house_number)
            ).collect(),
        )
        if collected.height == 0 and street and city:
            # Source-side postcode typos (one bad character) were dropping otherwise-valid
            # listings into the DLQ — retry on the same fields the no-postcode branch uses.
            logger.debug(
                f"Postcode {postcode} matched no BAG rows; retrying with street+number+city "
                f"({street} {house_number}, {city})"
            )
            return self._collect_by_street_number_city(df, street, house_number, city)
        return collected

    @staticmethod
    def _collect_by_street_number_city(
        df: pl.LazyFrame,
        street: str | None,
        house_number: int,
        city: str,
    ) -> pl.DataFrame:
        return cast(
            pl.DataFrame,
            df.filter(
                (pl.col("straatnaam").str.to_lowercase() == (street or "").lower())
                & (pl.col("huisnummer") == house_number)
                & (pl.col("woonplaats").str.to_lowercase() == _canonicalise_city(city).lower())
            ).collect(),
        )

    @staticmethod
    def _filter_exact_pair(
        candidates: pl.DataFrame,
        house_letter: str | None,
        house_number_suffix: str | None,
    ) -> pl.DataFrame:
        # Treats a None input as "match the NULL row" — that's how a
        # "Hoofdstraat 12 bis" listing (house_letter=None, suffix="bis")
        # binds to the unique BAG row with huisletter NULL and
        # huisnummertoevoeging "bis", and how a bare "Neuweg 14" listing
        # (both None) collapses onto the building's main NULL/NULL row.
        return candidates.filter(
            _column_matches("huisletter", house_letter) & _column_matches("huisnummertoevoeging", house_number_suffix)
        )

    @staticmethod
    def _filter_by_toevoeging_digits(
        candidates: pl.DataFrame,
        house_letter: str | None,
        house_number_suffix: str,
    ) -> pl.DataFrame:
        # Conservative retry: only fires when the suffix is purely numeric so
        # "302" can collapse onto BAG's "V302" without "A302" doing the same.
        # The house_letter side is still strict — V302 has huisletter NULL, so
        # an input house_letter of "A" must NOT pull V302 in.
        return candidates.filter(
            _column_matches("huisletter", house_letter)
            & (pl.col("huisnummertoevoeging").str.replace_all(r"\D", "") == house_number_suffix)
        )

    @staticmethod
    def _filter_by_city(candidates: pl.DataFrame, city: str) -> pl.DataFrame:
        return candidates.filter(pl.col("woonplaats").str.to_lowercase() == _canonicalise_city(city).lower())

    @staticmethod
    def _filter_main_address(candidates: pl.DataFrame) -> pl.DataFrame:
        return candidates.filter(pl.col("huisletter").is_null() & pl.col("huisnummertoevoeging").is_null())

    @staticmethod
    def _to_match(candidates: pl.DataFrame) -> BagMatch:
        row = candidates.row(0, named=True)
        return BagMatch(
            bag_id=row["nummeraanduiding_id"],
            postcode=row["postcode"],
            street=row["straatnaam"],
            house_number=row["huisnummer"],
            house_letter=row["huisletter"],
            house_number_suffix=row["huisnummertoevoeging"],
            city=row["woonplaats"],
        )


def _column_matches(column: str, value: str | None) -> pl.Expr:
    if value is None:
        return pl.col(column).is_null()
    return pl.col(column).str.to_uppercase() == value.upper()


def apply_bag_match(listing: Listing, match: BagMatch | None) -> None:
    if match is None:
        return
    listing.bag_id = match.bag_id
    if listing.postcode is None:
        listing.postcode = match.postcode
    if listing.street is None:
        listing.street = match.street
    if listing.house_number is None:
        listing.house_number = match.house_number
    if listing.house_letter is None:
        listing.house_letter = match.house_letter
    if listing.house_number_suffix is None:
        listing.house_number_suffix = match.house_number_suffix
    if match.city:
        listing.city = match.city
