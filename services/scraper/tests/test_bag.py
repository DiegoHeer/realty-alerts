from pathlib import Path

import polars as pl
import pytest

from scraper.bag import ParquetBagLookup


@pytest.fixture
def bag_parquet(tmp_path: Path) -> Path:
    """Tiny parquet that mirrors the real BAG schema, covering the lookup branches."""
    df = pl.DataFrame(
        {
            "nummeraanduiding_id": [
                "0003200000133985",
                "0003200000133986",
                "0003200000133987",
                "0003200000133988",
                "0003200000200001",
                "0003200000200002",
                "0003200000300001",
            ],
            "huisnummer": pl.Series([3, 5, 5, 5, 12, 12, 7], dtype=pl.Int32),
            "huisletter": [None, None, "A", None, None, None, None],
            "huisnummertoevoeging": [None, None, None, "bis", None, None, None],
            "postcode": [
                "9901AA",
                "9901AA",
                "9901AA",
                "9901AA",
                "1011AB",
                "1011AB",
                "1234CD",
            ],
            "straatnaam": [
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Damrak",
                "Damrak",
                "Hoofdstraat",
            ],
            "woonplaats": [
                "Appingedam",
                "Appingedam",
                "Appingedam",
                "Appingedam",
                "Amsterdam",
                "Haarlem",
                "Utrecht",
            ],
        }
    )
    path = tmp_path / "bag.parquet"
    df.write_parquet(path)
    return path


def test_exact_postcode_match(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Snelgersmastraat",
                house_number=3,
                suffix=None,
                postcode="9901 AA",
                city="Appingedam",
            )
            == "0003200000133985"
        )


def test_postcode_normalisation_with_space(bag_parquet: Path) -> None:
    """parse_dutch_postcode emits '9901 AA' but parquet stores '9901AA'."""
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street=None,
                house_number=3,
                suffix=None,
                postcode="9901 AA",
                city="Appingedam",
            )
            == "0003200000133985"
        )


def test_postcode_normalisation_lowercase(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street=None,
                house_number=3,
                suffix=None,
                postcode="9901 aa",
                city="Appingedam",
            )
            == "0003200000133985"
        )


def test_disambiguation_by_huisletter(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Snelgersmastraat",
                house_number=5,
                suffix="A",
                postcode="9901 AA",
                city="Appingedam",
            )
            == "0003200000133987"
        )


def test_disambiguation_by_huisnummertoevoeging(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Snelgersmastraat",
                house_number=5,
                suffix="bis",
                postcode="9901 AA",
                city="Appingedam",
            )
            == "0003200000133988"
        )


def test_disambiguation_by_city_when_no_suffix(bag_parquet: Path) -> None:
    """Same postcode+huisnummer in two cities — pick by woonplaats."""
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Damrak",
                house_number=12,
                suffix=None,
                postcode="1011 AB",
                city="Haarlem",
            )
            == "0003200000200002"
        )


def test_no_match_returns_none(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Nonexistent",
                house_number=999,
                suffix=None,
                postcode="0000 ZZ",
                city="Nowhere",
            )
            is None
        )


def test_missing_house_number_short_circuits(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Snelgersmastraat",
                house_number=None,
                suffix=None,
                postcode="9901 AA",
                city="Appingedam",
            )
            is None
        )


def test_postcode_missing_falls_back_to_street_city(bag_parquet: Path) -> None:
    """VastgoedNL cards have no postcode — match via straatnaam + huisnummer + woonplaats."""
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup_bag_id(
                street="Hoofdstraat",
                house_number=7,
                suffix=None,
                postcode=None,
                city="Utrecht",
            )
            == "0003200000300001"
        )


def test_ambiguous_returns_none(bag_parquet: Path) -> None:
    """Multiple matches that suffix and city can't disambiguate."""
    with ParquetBagLookup(bag_parquet) as bag:
        # huisnummer=5 at 9901AA has 3 candidates (no suffix, "A", "bis"); suffix doesn't match any
        assert (
            bag.lookup_bag_id(
                street="Snelgersmastraat",
                house_number=5,
                suffix="X",
                postcode="9901 AA",
                city="Appingedam",
            )
            is None
        )


def test_close_clears_cached_frame(bag_parquet: Path) -> None:
    bag = ParquetBagLookup(bag_parquet)
    bag.lookup_bag_id(street=None, house_number=3, suffix=None, postcode="9901 AA", city="Appingedam")
    assert bag._df is not None
    bag.close()
    assert bag._df is None


def test_context_manager_calls_close(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        bag.lookup_bag_id(street=None, house_number=3, suffix=None, postcode="9901 AA", city="Appingedam")
        assert bag._df is not None
    assert bag._df is None
