from typing import Any

from scraper.bag import BagMissReason
from scraper.enums import Website
from scraper.models import DeadListing, Listing
from scraper.runner import _classify_dead_reason


def _listing(**overrides: Any) -> Listing:
    defaults: dict[str, Any] = {
        "detail_url": "https://example.com/x",
        "title": "Klaterweg 9 R A59",
        "price": "€ 250.000",
        "city": "Huizen",
        "website": Website.PARARIUS,
    }
    return Listing(**{**defaults, **overrides})


def test_classify_dead_reason_returns_parse_failed_when_house_number_missing() -> None:
    listing = _listing(house_number=None, street=None)
    assert _classify_dead_reason(listing, BagMissReason.MISSING_HOUSE_NUMBER) == "parse_failed"


def test_classify_dead_reason_passes_through_bag_no_match() -> None:
    listing = _listing(house_number=9, street="Klaterweg")
    assert _classify_dead_reason(listing, BagMissReason.NO_MATCH) == "bag_no_match"


def test_classify_dead_reason_passes_through_bag_ambiguous() -> None:
    listing = _listing(house_number=9, street="Klaterweg")
    assert _classify_dead_reason(listing, BagMissReason.AMBIGUOUS) == "bag_ambiguous"


def test_from_listing_drops_enrichment_fields() -> None:
    """DeadListing mirrors the API's DeadListingIn schema 1:1 — bag_id and the
    property metadata are populated by the matcher and have no place on a row
    that didn't match."""
    listing = _listing(
        street="Klaterweg",
        house_number=9,
        house_letter="R",
        house_number_suffix="A59",
        postcode="1271KE",
        bag_id="0501100000000001",
        property_type="apartment",
        bedrooms=2,
        area_sqm=70.0,
        image_url="https://example.com/img.jpg",
    )
    dead = DeadListing.from_listing(listing, reason="bag_no_match")
    payload = dead.model_dump()
    assert payload["reason"] == "bag_no_match"
    assert payload["street"] == "Klaterweg"
    assert payload["house_letter"] == "R"
    assert payload["house_number_suffix"] == "A59"
    assert "bag_id" not in payload
    assert "property_type" not in payload
    assert "bedrooms" not in payload
    assert "area_sqm" not in payload
