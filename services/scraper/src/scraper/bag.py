from pathlib import Path
from typing import Self

import polars as pl
from loguru import logger

BAG_DATA_PATH = Path(__file__).resolve().parent / "data" / "bag_addresses.parquet"


def _normalise_postcode(postcode: str) -> str:
    return postcode.upper().replace(" ", "")


class ParquetBagLookup:
    """Temporary BAG lookup backed by a local parquet snapshot.

    Interface (lookup_bag_id, context-manager protocol) is intentionally
    compatible with the planned HTTP client, so runner.py only changes
    its constructor call when the BAG API key arrives.
    """

    def __init__(self, parquet_path: Path = BAG_DATA_PATH) -> None:
        self._path = parquet_path
        self._df: pl.DataFrame | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._df = None

    def lookup_bag_id(
        self,
        *,
        street: str | None,
        house_number: int | None,
        suffix: str | None,
        postcode: str | None,
        city: str,
    ) -> str | None:
        if house_number is None:
            return None

        candidates = self._find_candidates(street, house_number, postcode, city)
        if candidates.height == 0:
            return None
        if candidates.height == 1:
            return self._first_id(candidates)

        if suffix:
            disambiguated = self._filter_by_suffix(candidates, suffix)
            if disambiguated.height == 1:
                return self._first_id(disambiguated)

        by_city = self._filter_by_city(candidates, city)
        if by_city.height == 1:
            return self._first_id(by_city)

        logger.warning(
            f"Ambiguous BAG match for {postcode} {house_number}{suffix or ''} {city}: {candidates.height} candidates"
        )
        return None

    def _df_loaded(self) -> pl.DataFrame:
        if self._df is None:
            logger.info(f"Loading BAG parquet from {self._path}")
            self._df = pl.read_parquet(self._path).with_columns(
                pl.col("postcode").str.to_uppercase().str.replace_all(" ", "")
            )
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
            return df.filter(
                (pl.col("postcode") == _normalise_postcode(postcode)) & (pl.col("huisnummer") == house_number)
            )
        return df.filter(
            (pl.col("straatnaam").str.to_lowercase() == (street or "").lower())
            & (pl.col("huisnummer") == house_number)
            & (pl.col("woonplaats").str.to_lowercase() == city.lower())
        )

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
    def _first_id(candidates: pl.DataFrame) -> str:
        return candidates["nummeraanduiding_id"][0]
