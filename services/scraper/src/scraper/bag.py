from dataclasses import dataclass
from pathlib import Path
from typing import Self, cast

import polars as pl
from loguru import logger

from scraper.models import Listing

BAG_DATA_PATH = Path(__file__).resolve().parent / "data" / "bag_addresses.parquet"


def _normalise_postcode(postcode: str) -> str:
    return postcode.upper().replace(" ", "")


def _coalesce_suffix(huisletter: str | None, huisnummertoevoeging: str | None) -> str | None:
    if huisletter:
        return huisletter
    return huisnummertoevoeging or None


def _format_address(
    *,
    postcode: str | None,
    street: str | None,
    house_number: int,
    suffix: str | None,
    city: str | None,
) -> str:
    number = f"{house_number}-{suffix}" if suffix else str(house_number)
    return f"{postcode or '-'} {street or '-'} {number} {city or '-'}"


@dataclass(frozen=True, slots=True)
class BagMatch:
    bag_id: str
    postcode: str | None
    street: str | None
    house_number: int
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
        suffix: str | None,
        postcode: str | None,
        city: str,
    ) -> BagMatch | None:
        if house_number is None:
            return None

        address = _format_address(postcode=postcode, street=street, house_number=house_number, suffix=suffix, city=city)
        candidates = self._find_candidates(street, house_number, postcode, city)
        if candidates.height == 0:
            logger.warning(f"No BAG match for {address}")
            return None
        if candidates.height == 1:
            return self._to_match(candidates)

        if suffix:
            disambiguated = self._filter_by_suffix(candidates, suffix)
            if disambiguated.height == 1:
                return self._to_match(disambiguated)

        by_city = self._filter_by_city(candidates, city)
        if by_city.height == 1:
            return self._to_match(by_city)

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
    def _filter_by_suffix(candidates: pl.DataFrame, suffix: str) -> pl.DataFrame:
        s = suffix.upper().strip()
        return candidates.filter(
            (pl.col("huisletter").str.to_uppercase() == s) | (pl.col("huisnummertoevoeging").str.to_uppercase() == s)
        )

    @staticmethod
    def _filter_by_city(candidates: pl.DataFrame, city: str) -> pl.DataFrame:
        return candidates.filter(pl.col("woonplaats").str.to_lowercase() == city.lower())

    @staticmethod
    def _to_match(candidates: pl.DataFrame) -> BagMatch:
        row = candidates.row(0, named=True)
        return BagMatch(
            bag_id=row["nummeraanduiding_id"],
            postcode=row["postcode"],
            street=row["straatnaam"],
            house_number=row["huisnummer"],
            house_number_suffix=_coalesce_suffix(row["huisletter"], row["huisnummertoevoeging"]),
            city=row["woonplaats"],
        )


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
    if listing.house_number_suffix is None:
        listing.house_number_suffix = match.house_number_suffix
