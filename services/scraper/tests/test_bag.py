from collections.abc import Iterator
from pathlib import Path

import polars as pl
import pytest
from loguru import logger

from scraper.bag import BagMatch, ParquetBagLookup, apply_bag_match
from scraper.enums import Website
from scraper.models import Listing


@pytest.fixture
def loguru_caplog(caplog: pytest.LogCaptureFixture) -> Iterator[pytest.LogCaptureFixture]:
    handler_id = logger.add(caplog.handler, format="{message}", level="INFO")
    caplog.set_level("INFO")
    yield caplog
    logger.remove(handler_id)


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
                # Parkweg-style cluster: 1 main row + V-prefixed unit numbers.
                "0402200000600001",
                "0402200000600101",
                "0402200000600302",
                "0402200000600521",
                # No-main-row cluster: only letter/toevoeging suffixes, used to
                # exercise the truly-ambiguous case where the building-level
                # fallback can't find a NULL/NULL row.
                "0003200000700001",
                "0003200000700002",
                # Klaterweg-style: huisletter + huisnummertoevoeging both set,
                # plus a sibling row that shares the huisletter to prove the
                # 2-column exact match (not just huisletter) wins.
                "0501100000000001",
                "0501100000000002",
                # 's-Gravenhage row reachable from a "Den Haag" query — covers
                # both the alias map (woonplaats filter) and the canonical-city
                # writeback in apply_bag_match.
                "0518100000000001",
            ],
            "huisnummer": pl.Series([3, 5, 5, 5, 12, 12, 7, 2, 2, 2, 2, 20, 20, 9, 9, 1], dtype=pl.Int32),
            "huisletter": [
                None,
                None,
                "A",
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "A",
                "B",
                "R",
                "R",
                None,
            ],
            "huisnummertoevoeging": [
                None,
                None,
                None,
                "bis",
                None,
                None,
                None,
                None,
                "V101",
                "V302",
                "V521",
                None,
                None,
                "A59",
                "A60",
                None,
            ],
            "postcode": [
                "9901AA",
                "9901AA",
                "9901AA",
                "9901AA",
                "1011AB",
                "1011AB",
                "1234CD",
                "3221LV",
                "3221LV",
                "3221LV",
                "3221LV",
                "9901AA",
                "9901AA",
                "1271KE",
                "1271KE",
                "2511AA",
            ],
            "straatnaam": [
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Damrak",
                "Damrak",
                "Hoofdstraat",
                "Parkweg",
                "Parkweg",
                "Parkweg",
                "Parkweg",
                "Snelgersmastraat",
                "Snelgersmastraat",
                "Klaterweg",
                "Klaterweg",
                "Plein",
            ],
            "woonplaats": [
                "Appingedam",
                "Appingedam",
                "Appingedam",
                "Appingedam",
                "Amsterdam",
                "Haarlem",
                "Utrecht",
                "Hellevoetsluis",
                "Hellevoetsluis",
                "Hellevoetsluis",
                "Hellevoetsluis",
                "Appingedam",
                "Appingedam",
                "Huizen",
                "Huizen",
                "'s-Gravenhage",
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
            house_letter=None,
            house_number_suffix=None,
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
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133985"


def test_postcode_normalisation_lowercase(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street=None,
            house_number=3,
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 aa",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133985"


def test_disambiguation_by_house_letter(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            house_letter="A",
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133987"


def test_disambiguation_by_huisnummertoevoeging(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            house_letter=None,
            house_number_suffix="bis",
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
            house_letter=None,
            house_number_suffix=None,
            postcode="1011 AB",
            city="Haarlem",
        )
    assert _bag_id(match) == "0003200000200002"


def test_missing_house_number_short_circuits(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup(
                street="Snelgersmastraat",
                house_number=None,
                house_letter=None,
                house_number_suffix=None,
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
            house_letter=None,
            house_number_suffix=None,
            postcode=None,
            city="Utrecht",
        )
    assert _bag_id(match) == "0003200000300001"


def test_ambiguous_returns_none(bag_parquet: Path) -> None:
    """Multiple suffixed candidates and no main row to fall back on → None."""
    with ParquetBagLookup(bag_parquet) as bag:
        # huisnummer=20 at 9901AA has 2 candidates (huisletter A and B) and
        # no NULL/NULL main row; house_letter "X" matches neither.
        assert (
            bag.lookup(
                street="Snelgersmastraat",
                house_number=20,
                house_letter="X",
                house_number_suffix=None,
                postcode="9901 AA",
                city="Appingedam",
            )
            is None
        )


def test_no_suffix_prefers_main_row_among_siblings(bag_parquet: Path) -> None:
    """Pararius "Neuweg 14" case: no suffix scraped, multiple candidates share
    postcode and city, but only one is the bare main address."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133986"


def test_digit_suffix_matches_v_prefixed_huisnummertoevoeging(bag_parquet: Path) -> None:
    """Pararius "Parkweg 2 302" case: toevoeging "302" must match BAG's "V302"."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Parkweg",
            house_number=2,
            house_letter=None,
            house_number_suffix="302",
            postcode="3221 LV",
            city="Hellevoetsluis",
        )
    assert _bag_id(match) == "0402200000600302"


def test_digit_retry_respects_house_letter(bag_parquet: Path) -> None:
    """Digit normalisation must not pull V302 (huisletter NULL) when the input
    explicitly carries a house_letter — that mismatch should fall through to
    the building-level main row instead."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Parkweg",
            house_number=2,
            house_letter="A",
            house_number_suffix="302",
            postcode="3221 LV",
            city="Hellevoetsluis",
        )
    assert _bag_id(match) == "0402200000600001"


def test_house_letter_plus_toevoeging_does_exact_match(bag_parquet: Path) -> None:
    """Klaterweg-style: house_letter + toevoeging both populated must do a
    2-column exact match instead of accidentally returning a sibling that
    only shares the huisletter."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Klaterweg",
            house_number=9,
            house_letter="R",
            house_number_suffix="A59",
            postcode="1271 KE",
            city="Huizen",
        )
    assert _bag_id(match) == "0501100000000001"


def test_falls_back_to_main_row_for_unmatched_suffix(
    bag_parquet: Path,
    loguru_caplog: pytest.LogCaptureFixture,
) -> None:
    """When a house_letter is provided but matches no candidate, return the
    building's bare main row and log at info level so loose matches stay
    distinguishable."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            house_letter="X",
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert _bag_id(match) == "0003200000133986"
    assert any("BAG fallback to building-level match" in record.message for record in loguru_caplog.records)


def test_unmatched_suffix_without_main_row_still_warns(
    bag_parquet: Path,
    loguru_caplog: pytest.LogCaptureFixture,
) -> None:
    """If neither digit normalisation, city, nor a NULL/NULL row resolves the
    candidate set, the matcher returns None with the existing warning."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=20,
            house_letter="X",
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert match is None
    assert any("Ambiguous BAG match" in record.message for record in loguru_caplog.records)


def test_close_clears_cached_frame(bag_parquet: Path) -> None:
    bag = ParquetBagLookup(bag_parquet)
    bag.lookup(
        street=None,
        house_number=3,
        house_letter=None,
        house_number_suffix=None,
        postcode="9901 AA",
        city="Appingedam",
    )
    assert bag._df is not None
    bag.close()
    assert bag._df is None


def test_context_manager_calls_close(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        bag.lookup(
            street=None,
            house_number=3,
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
        assert bag._df is not None
    assert bag._df is None


def test_lookup_returns_bag_match_with_address_fields(bag_parquet: Path) -> None:
    """lookup returns the matched BAG row as a BagMatch, not just the bag_id."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=3,
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert match == BagMatch(
        bag_id="0003200000133985",
        postcode="9901AA",
        street="Snelgersmastraat",
        house_number=3,
        huisletter=None,
        house_number_suffix=None,
        city="Appingedam",
    )


def test_lookup_no_match_returns_none(bag_parquet: Path) -> None:
    with ParquetBagLookup(bag_parquet) as bag:
        assert (
            bag.lookup(
                street="Nonexistent",
                house_number=999,
                house_letter=None,
                house_number_suffix=None,
                postcode="0000 ZZ",
                city="Nowhere",
            )
            is None
        )


def test_bag_match_exposes_huisletter_and_toevoeging_separately(tmp_path: Path) -> None:
    """A BAG row with both columns set surfaces both on BagMatch — no coalesce."""
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
            house_letter="B",
            house_number_suffix="bis",
            postcode="2000 AA",
            city="Testdorp",
        )
    assert match is not None
    assert match.huisletter == "B"
    assert match.house_number_suffix == "bis"


def test_lookup_suffix_falls_back_to_huisnummertoevoeging(bag_parquet: Path) -> None:
    """The 'bis' row has no huisletter — BagMatch.house_number_suffix == 'bis'."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Snelgersmastraat",
            house_number=5,
            house_letter=None,
            house_number_suffix="bis",
            postcode="9901 AA",
            city="Appingedam",
        )
    assert match is not None
    assert match.huisletter is None
    assert match.house_number_suffix == "bis"


def test_lookup_tolerates_null_postcode_in_matched_row(tmp_path: Path) -> None:
    """~3% of BAG rows have null postcode — must not raise during BagMatch construction."""
    df = pl.DataFrame(
        {
            "nummeraanduiding_id": ["0003200000500001"],
            "huisnummer": pl.Series([1], dtype=pl.Int32),
            "huisletter": pl.Series([None], dtype=pl.String),
            "huisnummertoevoeging": pl.Series([None], dtype=pl.String),
            "postcode": pl.Series([None], dtype=pl.String),
            "straatnaam": ["Nullstraat"],
            "woonplaats": ["Nulldorp"],
        }
    )
    path = tmp_path / "bag-null-postcode.parquet"
    df.write_parquet(path)
    with ParquetBagLookup(path) as bag:
        match = bag.lookup(
            street="Nullstraat",
            house_number=1,
            house_letter=None,
            house_number_suffix=None,
            postcode=None,
            city="Nulldorp",
        )
    assert match is not None
    assert match.bag_id == "0003200000500001"
    assert match.postcode is None


def test_lookup_warns_when_no_match(bag_parquet: Path, loguru_caplog: pytest.LogCaptureFixture) -> None:
    """A failed lookup should leave a breadcrumb so unmatched listings can be investigated."""
    with ParquetBagLookup(bag_parquet) as bag:
        bag.lookup(
            street="Nonexistent",
            house_number=999,
            house_letter=None,
            house_number_suffix=None,
            postcode="0000 ZZ",
            city="Nowhere",
        )
    assert any("No BAG match" in record.message for record in loguru_caplog.records)


def test_lookup_silent_when_house_number_missing(bag_parquet: Path, loguru_caplog: pytest.LogCaptureFixture) -> None:
    """Missing house_number is a missing-input case, not a BAG miss — don't log."""
    with ParquetBagLookup(bag_parquet) as bag:
        bag.lookup(
            street="Snelgersmastraat",
            house_number=None,
            house_letter=None,
            house_number_suffix=None,
            postcode="9901 AA",
            city="Appingedam",
        )
    assert not any("No BAG match" in record.message for record in loguru_caplog.records)


def test_den_haag_alias_resolves_via_no_postcode_fallback(bag_parquet: Path) -> None:
    """A VastgoedNL-style listing without a postcode lookups by street + city;
    "Den Haag" must alias to BAG's canonical "'s-Gravenhage" or the row is missed."""
    with ParquetBagLookup(bag_parquet) as bag:
        match = bag.lookup(
            street="Plein",
            house_number=1,
            house_letter=None,
            house_number_suffix=None,
            postcode=None,
            city="Den Haag",
        )
    assert match is not None
    assert match.bag_id == "0518100000000001"
    assert match.city == "'s-Gravenhage"


def _vastgoed_listing(
    *,
    postcode: str | None = None,
    street: str | None = "Snelgersmastraat",
    house_number: int | None = 3,
    house_letter: str | None = None,
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
        house_letter=house_letter,
        house_number_suffix=house_number_suffix,
        postcode=postcode,
        image_url=None,
        website=website,
    )


def _example_match(
    *,
    huisletter: str | None = None,
    house_number_suffix: str | None = None,
) -> BagMatch:
    return BagMatch(
        bag_id="0003200000133985",
        postcode="9901AA",
        street="Snelgersmastraat",
        house_number=3,
        huisletter=huisletter,
        house_number_suffix=house_number_suffix,
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


def test_apply_bag_match_writes_back_house_letter_and_toevoeging() -> None:
    """When the listing didn't carry these fields, the matched BAG row's
    canonical pair is propagated through so the persisted row shows both."""
    listing = _vastgoed_listing()
    apply_bag_match(listing, _example_match(huisletter="R", house_number_suffix="A59"))
    assert listing.house_letter == "R"
    assert listing.house_number_suffix == "A59"


def test_apply_bag_match_does_not_overwrite_scraped_house_letter() -> None:
    listing = _vastgoed_listing(house_letter="R", house_number_suffix="A59")
    apply_bag_match(listing, _example_match(huisletter="X", house_number_suffix="X99"))
    assert listing.house_letter == "R"
    assert listing.house_number_suffix == "A59"


def test_apply_bag_match_overwrites_city_to_canonical() -> None:
    """BAG is the canonical source for woonplaats — apply_bag_match always
    overwrites listing.city, even when the scraper emitted the colloquial form."""
    listing = Listing(
        detail_url="https://example.com/123",
        title="Plein 1",
        price="€ 250.000",
        city="Den Haag",
        street="Plein",
        house_number=1,
        postcode="2511AA",
        image_url=None,
        website=Website.PARARIUS,
    )
    match = BagMatch(
        bag_id="0518100000000001",
        postcode="2511AA",
        street="Plein",
        house_number=1,
        huisletter=None,
        house_number_suffix=None,
        city="'s-Gravenhage",
    )
    apply_bag_match(listing, match)
    assert listing.city == "'s-Gravenhage"
