from pathlib import Path

import polars as pl
import pytest

from scraper.bag import BagMatch, ParquetBagLookup, apply_bag_match
from scraper.enums import Website
from scraper.models import Listing


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


def _bag_id(match: BagMatch | None) -> str | None:
    return match.bag_id if match else None


def test_exact_postcode_match(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=3,
            suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133985"


def test_postcode_normalisation_with_space(bag_parquet: Path) -> None:
    """parse_dutch_postcode emits '9901 AA' but parquet stores '9901AA'."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street=None,
            house_number=3,
            suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133985"


def test_postcode_normalisation_lowercase(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street=None,
            house_number=3,
            suffix=None,
            postcode="9901 aa",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133985"


def test_disambiguation_by_huisletter(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            suffix="A",
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133987"


def test_disambiguation_by_huisnummertoevoeging(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            suffix="bis",
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133988"


def test_disambiguation_by_city_when_no_suffix(bag_parquet: Path) -> None:
    """Same postcode+huisnummer in two cities — pick by woonplaats."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Damrak",
            house_number=12,
            suffix=None,
            postcode="1011 AB",
            city="Haarlem",
        )
    assert _bag_id(match) == "0003200000200002"


def test_no_match_returns_none(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup(
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
            bag.lookup(
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
        match = bag.lookup(
            street="Hoofdstraat",
            house_number=7,
            suffix=None,
            postcode=None,
            city="Utrecht",
        )
    assert _bag_id(match) == "0003200000300001"


def test_ambiguous_returns_none(bag_parquet: Path) -> None:
    """Multiple matches that suffix and city can't disambiguate."""
    with ParquetBagLookup(bag_parquet) as bag:
        # huisnummer=5 at 9901AA has 3 candidates (no suffix, "A", "bis"); suffix doesn't match any
        assert (
            bag.lookup(
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
    bag.lookup(street=None, house_number=3, suffix=None, postcode="9901 AA", city="Appingedam")
    assert bag._df is not None
    bag.close()
    assert bag._df is None


def test_context_manager_calls_close(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        bag.lookup(street=None, house_number=3, suffix=None, postcode="9901 AA", city="Appingedam")
        assert bag._df is not None
    assert bag._df is None


def test_lookup_returns_bag_match_with_address_fields(bag_parquet: Path) -> None:
    """lookup returns the matched BAG row as a BagMatch, not just the bag_id."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=3,
            suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert match == BagMatch(
        bag_id="0003200000133985",
        postcode="9901AA",
        street="Snelgersmastraat",
        house_number=3,
        house_number_suffix=None,
        city="Appingedam",
    )


def test_lookup_no_match_returns_none(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup(
                street="Nonexistent",
                house_number=999,
                suffix=None,
                postcode="0000 ZZ",
                city="Nowhere",
            )
            is None
        )


def test_lookup_suffix_prefers_huisletter_over_huisnummertoevoeging(tmp_path: Path) -> None:
    """When a BAG row has both huisletter and huisnummertoevoeging, BagMatch picks huisletter."""
    df = pl.DataFrame(
        {
            "nummeraanduiding_id": ["0003200000400001"],
            "huisnummer": pl.Series([10], dtype=pl.Int32),
            "huisletter": ["B"],
            "huisnummertoevoeging": ["bis"],
            "postcode": ["2000AA"],
            "straatnaam": ["Teststraat"],
            "woonplaats": ["Testdorp"],
        }
    )
    path = tmp_path / "bag-suffix.parquet"
    df.write_parquet(path)
    with ParquetBagLookup(path) as bag:
        match = bag.lookup(
            street="Teststraat",
            house_number=10,
            suffix=None,
            postcode="2000 AA",
            city="Testdorp",
        )
    assert match is not None
    assert match.house_number_suffix == "B"


def test_lookup_suffix_falls_back_to_huisnummertoevoeging(bag_parquet: Path) -> None:
    """The 'bis' row has no huisletter — BagMatch.house_number_suffix == 'bis'."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            suffix="bis",
            postcode="9901 AA",
            city="Appingedam",
        )
    assert match is not None
    assert match.house_number_suffix == "bis"


def test_lookup_warns_when_no_match(bag_parquet: Path, caplog: pytest.LogCaptureFixture) -> None:
    """A failed lookup should leave a breadcrumb so unmatched listings can be investigated."""
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}", level="WARNING")
    try:
        with ParquetBagLookup(bag_parquet) as bag:
            bag.lookup(
                street="Nonexistent",
                house_number=999,
                suffix=None,
                postcode="0000 ZZ",
                city="Nowhere",
            )
    finally:
        logger.remove(handler_id)
    assert any("No BAG match" in record.message for record in caplog.records)


def test_lookup_silent_when_house_number_missing(bag_parquet: Path, caplog: pytest.LogCaptureFixture) -> None:
    """Missing house_number is a missing-input case, not a BAG miss — don't log."""
    from loguru import logger

    handler_id = logger.add(caplog.handler, format="{message}", level="WARNING")
    try:
        with ParquetBagLookup(bag_parquet) as bag:
            bag.lookup(
                street="Snelgersmastraat",
                house_number=None,
                suffix=None,
                postcode="9901 AA",
                city="Appingedam",
            )
    finally:
        logger.remove(handler_id)
    assert not any("No BAG match" in record.message for record in caplog.records)


def _vastgoed_listing(
    *,
    postcode: str | None = None,
    street: str | None = "Snelgersmastraat",
    house_number: int | None = 3,
    house_number_suffix: str | None = None,
    website: Website = Website.VASTGOED_NL,
) -> Listing:
    return Listing(
        detail_url="https://example.com/123",
        title="Snelgersmastraat 3",
        price="€ 250.000",
        city="Appingedam",
        street=street,
        house_number=house_number,
        house_number_suffix=house_number_suffix,
        postcode=postcode,
        image_url=None,
        website=website,
    )


def _example_match() -> BagMatch:
    return BagMatch(
        bag_id="0003200000133985",
        postcode="9901AA",
        street="Snelgersmastraat",
        house_number=3,
        house_number_suffix=None,
        city="Appingedam",
    )


def test_apply_bag_match_fills_missing_postcode() -> None:
    listing = _vastgoed_listing()
    apply_bag_match(listing, _example_match())
    assert listing.bag_id == "0003200000133985"
    assert listing.postcode == "9901AA"


def test_apply_bag_match_does_not_overwrite_scraped_postcode() -> None:
    listing = _vastgoed_listing(postcode="1234XX", website=Website.FUNDA)
    apply_bag_match(listing, _example_match())
    assert listing.bag_id == "0003200000133985"
    assert listing.postcode == "1234XX"


def test_apply_bag_match_no_match_leaves_listing_untouched() -> None:
    listing = _vastgoed_listing()
    apply_bag_match(listing, None)
    assert listing.bag_id is None
    assert listing.postcode is None
    assert listing.street == "Snelgersmastraat"
