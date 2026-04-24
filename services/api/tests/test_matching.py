import uuid

from app.matching.engine import _listing_matches_filter
from app.models.filter import UserFilter
from app.models.listing import Listing
from enums import ListingStatus, Website


def _make_listing(**overrides) -> Listing:
    defaults = {
        "id": 1,
        "website": Website.FUNDA,
        "detail_url": "https://example.com/listing/1",
        "title": "Test Listing",
        "price": "€ 350.000 k.k.",
        "price_cents": 350000,
        "city": "Amsterdam",
        "property_type": "apartment",
        "bedrooms": 2,
        "area_sqm": 75.0,
        "status": ListingStatus.ACTIVE,
    }
    return Listing(**{**defaults, **overrides})


def _make_filter(**overrides) -> UserFilter:
    defaults = {
        "id": 1,
        "user_id": uuid.uuid4(),
        "name": "Test Filter",
        "is_active": True,
    }
    return UserFilter(**{**defaults, **overrides})


def test_listing_matches_empty_filter():
    listing = _make_listing()
    f = _make_filter()
    assert _listing_matches_filter(listing, f) is True


def test_listing_matches_city():
    listing = _make_listing(city="Amsterdam")
    f = _make_filter(city="Amsterdam")
    assert _listing_matches_filter(listing, f) is True


def test_listing_rejects_wrong_city():
    listing = _make_listing(city="Amsterdam")
    f = _make_filter(city="Rotterdam")
    assert _listing_matches_filter(listing, f) is False


def test_listing_matches_price_range():
    listing = _make_listing(price_cents=300000)
    f = _make_filter(min_price=200000, max_price=400000)
    assert _listing_matches_filter(listing, f) is True


def test_listing_rejects_below_min_price():
    listing = _make_listing(price_cents=100000)
    f = _make_filter(min_price=200000)
    assert _listing_matches_filter(listing, f) is False


def test_listing_rejects_above_max_price():
    listing = _make_listing(price_cents=500000)
    f = _make_filter(max_price=400000)
    assert _listing_matches_filter(listing, f) is False


def test_listing_with_none_price_cents_skips_price_filter():
    listing = _make_listing(price_cents=None)
    f = _make_filter(min_price=200000, max_price=400000)
    assert _listing_matches_filter(listing, f) is True


def test_listing_matches_bedrooms():
    listing = _make_listing(bedrooms=3)
    f = _make_filter(min_bedrooms=2)
    assert _listing_matches_filter(listing, f) is True


def test_listing_rejects_insufficient_bedrooms():
    listing = _make_listing(bedrooms=1)
    f = _make_filter(min_bedrooms=2)
    assert _listing_matches_filter(listing, f) is False


def test_listing_matches_website_filter():
    listing = _make_listing(website=Website.FUNDA)
    f = _make_filter(websites=["funda", "pararius"])
    assert _listing_matches_filter(listing, f) is True


def test_listing_rejects_wrong_website():
    listing = _make_listing(website=Website.FUNDA)
    f = _make_filter(websites=["pararius"])
    assert _listing_matches_filter(listing, f) is False
