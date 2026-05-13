from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest
import respx
from django.contrib import messages

from scraping.resolvers import create_resolver
from scraping.resolvers.kadaster import BAG_BASE_URL
from scraping.models import BagStatus, Listing, ListingStatus, Residence
from tests.factories import ListingFactory, ResidenceFactory


def _failed_listing(**overrides) -> Listing:
    defaults = {
        "residence": None,
        "bag_status": BagStatus.BAG_NO_MATCH,
        "bag_failure_reason": "BAG lookup: no_match",
        "postcode": "1271 KE",
        "house_number": 9,
        "house_letter": None,
        "house_number_suffix": None,
        "city": "Huizen",
        "street": "Klaterweg",
        "price_eur": 425_000,
        "status": ListingStatus.NEW,
    }
    defaults.update(overrides)
    return cast(Listing, ListingFactory(**defaults))


def _bag_address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Klaterweg",
        "huisnummer": 9,
        "postcode": "1271KE",
        "woonplaatsNaam": "Huizen",
        "nummeraanduidingIdentificatie": "0402200000084467",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _promote_listing
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@respx.mock
def test_promote_listing_resolves_listing_and_creates_residence(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    listing = _failed_listing()

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is None
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.bag_resolved_at is not None
    assert listing.bag_failure_reason == ""
    assert listing.residence is not None
    assert listing.residence.bag_id == "0402200000084467"
    assert listing.residence.city == "Huizen"
    assert listing.residence.street == "Klaterweg"


@pytest.mark.django_db
@respx.mock
def test_promote_listing_links_to_existing_residence_and_reconciles(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    existing = cast(Residence, ResidenceFactory(bag_id="0402200000084467", current_price_eur=600_000))
    listing = _failed_listing(price_eur=425_000)

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is None
    listing.refresh_from_db()
    assert listing.residence == existing
    existing.refresh_from_db()
    assert existing.current_price_eur == 425_000  # reconciled: min price


@pytest.mark.django_db
def test_promote_listing_skips_listing_not_in_failed_state(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    residence = cast(Residence, ResidenceFactory())
    listing = cast(
        Listing,
        ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED),
    )

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is not None
    assert "resolved" in error.lower()
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED  # unchanged


@pytest.mark.django_db
@respx.mock
def test_promote_listing_returns_error_on_no_match_and_updates_reason(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))
    listing = _failed_listing()

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is not None
    assert "no match" in error.lower()
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.BAG_NO_MATCH
    assert listing.residence is None


@pytest.mark.django_db
@respx.mock
def test_promote_listing_returns_error_on_ambiguous(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _bag_address(nummeraanduidingIdentificatie="0402200000000001"),
                        _bag_address(nummeraanduidingIdentificatie="0402200000000002"),
                    ]
                }
            },
        )
    )
    listing = _failed_listing()

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is not None
    assert "ambiguous" in error.lower()
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.BAG_AMBIGUOUS
    assert listing.residence is None


@pytest.mark.django_db
def test_promote_listing_returns_error_on_missing_address(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    # No respx mock — lookup must short-circuit before HTTP.
    listing = _failed_listing(postcode=None, street=None)

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is not None
    assert "address" in error.lower()
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.MISSING_ADDRESS
    assert listing.residence is None


@pytest.mark.django_db
@respx.mock
def test_promote_listing_returns_error_on_http_error(settings):
    from scraping.admin import _promote_listing

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    listing = _failed_listing()

    with create_resolver(api_key=settings.BAG_API_KEY) as resolver:
        error = _promote_listing(listing, resolver)

    assert error is not None
    assert "bag api error" in error.lower()
    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.BAG_NO_MATCH  # unchanged
    assert listing.residence is None


# ---------------------------------------------------------------------------
# promote_listings admin action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@respx.mock
def test_promote_listings_action_reports_success_count(settings):
    from scraping.admin import promote_listings

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    listings = [_failed_listing(), _failed_listing()]
    queryset = Listing.objects.filter(pk__in=[listing.pk for listing in listings])

    modeladmin = MagicMock()
    request = MagicMock()

    promote_listings(modeladmin, request, queryset)

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert len(success_calls) == 1
    assert "2" in success_calls[0].args[1]


@pytest.mark.django_db
@respx.mock
def test_promote_listings_action_reports_per_listing_failure(settings):
    from scraping.admin import promote_listings

    settings.BAG_API_KEY = "test-key"
    respx.get(f"{BAG_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))
    listing = _failed_listing()
    queryset = Listing.objects.filter(pk=listing.pk)

    modeladmin = MagicMock()
    request = MagicMock()

    promote_listings(modeladmin, request, queryset)

    warning_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.WARNING]
    assert len(warning_calls) == 1
    assert str(listing.pk) in warning_calls[0].args[1]


@pytest.mark.django_db
@respx.mock
def test_promote_listings_action_handles_mixed_batch(settings):
    """One successful, one ambiguous — correct message counts."""
    from scraping.admin import promote_listings

    settings.BAG_API_KEY = "test-key"
    good_listing = _failed_listing(postcode="1271 KE", house_number=9)
    bad_listing = _failed_listing(postcode=None, street=None)  # will hit missing_address

    # Route: good_listing hits postcode route, bad_listing short-circuits (no HTTP call needed).
    respx.get(f"{BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )

    queryset = Listing.objects.filter(pk__in=[good_listing.pk, bad_listing.pk])
    modeladmin = MagicMock()
    request = MagicMock()

    promote_listings(modeladmin, request, queryset)

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    warning_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.WARNING]
    assert len(success_calls) == 1
    assert "1" in success_calls[0].args[1]
    assert len(warning_calls) == 1
