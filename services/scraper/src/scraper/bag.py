from dataclasses import dataclass
from pathlib import Path
from typing import Self, cast

import polars as pl
from loguru import logger

from scraper.models import Listing

BAG_DATA_PATH = Path(__file__).resolve().parent / "data" / "bag_addresses.parquet"


def _normalise_postcode(postcode: str) -> str:
    return postcode.upper().replace(" ", "")


def _format_address(
    *,
    postcode: str | None,
    street: str | None,
    house_number: int,
    huisletter: str | None,
    huisnummertoevoeging: str | None,
    city: str | None,
) -> str:
    parts = [str(house_number)]
    if huisletter:
        parts.append(huisletter)
    if huisnummertoevoeging:
        parts.append(huisnummertoevoeging)
    number = "-".join(parts)
    return f"{postcode or '-'} {street or '-'} {number} {city or '-'}"


@dataclass(frozen=True, slots=True)
class BagMatch:
    bag_id: str
    postcode: str | None
    street: str | None
    house_number: int
    huisletter: str | None
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
    ) -> BagMatch | None:
        if house_number is None:
            return None

        address = _format_address(
            postcode=postcode,
            street=street,
            house_number=house_number,
            huisletter=house_letter,
            huisnummertoevoeging=house_number_suffix,
            city=city,
        )
        candidates = self._find_candidates(street, house_number, postcode, city)
        if candidates.height == 0:
            logger.warning(f"No BAG match for {address}")
            return None
        if candidates.height == 1:
            return self._to_match(candidates)
        return self._disambiguate(candidates, house_letter, house_number_suffix, city, address)

    def _disambiguate(
        self,
        candidates: pl.DataFrame,
        huisletter: str | None,
        toevoeging: str | None,
        city: str,
        address: str,
    ) -> BagMatch | None:
        exact = self._filter_exact_pair(candidates, huisletter, toevoeging)
        if exact.height == 1:
            return self._to_match(exact)

        if exact.height == 0 and toevoeging and toevoeging.isdigit():
            by_digits = self._filter_by_toevoeging_digits(candidates, huisletter, toevoeging)
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
        return None

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
        if postcode:
            collected = df.filter(
                (pl.col("postcode") == _normalise_postcode(postcode)) & (pl.col("huisnummer") == house_number)
            ).collect()
        else:
            collected = df.filter(
                (pl.col("straatnaam").str.to_lowercase() == (street or "").lower())
                & (pl.col("huisnummer") == house_number)
                & (pl.col("woonplaats").str.to_lowercase() == city.lower())
            ).collect()
        return cast(pl.DataFrame, collected)

    @staticmethod
    def _filter_exact_pair(
        candidates: pl.DataFrame,
        huisletter: str | None,
        toevoeging: str | None,
    ) -> pl.DataFrame:
        # Treats a None input as "match the NULL row" — that's how a
        # "Hoofdstraat 12 bis" listing (huisletter=None, toevoeging="bis")
        # binds to the unique BAG row with huisletter NULL and
        # huisnummertoevoeging "bis", and how a bare "Neuweg 14" listing
        # (both None) collapses onto the building's main NULL/NULL row.
        return candidates.filter(
            _column_matches("huisletter", huisletter) & _column_matches("huisnummertoevoeging", toevoeging)
        )

    @staticmethod
    def _filter_by_toevoeging_digits(
        candidates: pl.DataFrame,
        huisletter: str | None,
        toevoeging: str,
    ) -> pl.DataFrame:
        # Conservative retry: only fires when toevoeging is purely numeric so
        # "302" can collapse onto BAG's "V302" without "A302" doing the same.
        # The huisletter side is still strict — V302 has huisletter NULL, so
        # an input huisletter of "A" must NOT pull V302 in.
        return candidates.filter(
            _column_matches("huisletter", huisletter)
            & (pl.col("huisnummertoevoeging").str.replace_all(r"\D", "") == toevoeging)
        )

    @staticmethod
    def _filter_by_city(candidates: pl.DataFrame, city: str) -> pl.DataFrame:
        return candidates.filter(pl.col("woonplaats").str.to_lowercase() == city.lower())

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
            huisletter=row["huisletter"],
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
        listing.house_letter = match.huisletter
    if listing.house_number_suffix is None:
        listing.house_number_suffix = match.house_number_suffix
