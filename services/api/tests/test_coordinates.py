from io import StringIO
from typing import cast

import httpx
import pytest
import respx

from scraping.models import BagStatus, Listing, ListingStatus, Residence
from scraping.resolvers.coordinates import PdokCoordinateLookup
from tests.factories import ListingFactory, ResidenceFactory

_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_PDOK_FREE_URL = f"{_PDOK_BASE_URL}/free"
_BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"


def _pdok_coords_response(lon: float = 4.89348311, lat: float = 52.37588008) -> dict:
    return {"response": {"docs": [{"centroide_ll": f"POINT({lon} {lat})"}]}}


def _pdok_empty_response() -> dict:
    return {"response": {"docs": []}}


# --- PdokCoordinateLookup unit tests ---


@respx.mock
def test_lookup_returns_lat_lon_on_success():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_coords_response(4.893, 52.376)))
    lookup = PdokCoordinateLookup()
    try:
        result = lookup.lookup("0363200000218780")
    finally:
        lookup.close()
    assert result is not None
    lat, lon = result
    assert lat == pytest.approx(52.376)
    assert lon == pytest.approx(4.893)


@respx.mock
def test_lookup_returns_none_on_empty_docs():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_empty_response()))
    lookup = PdokCoordinateLookup()
    try:
        result = lookup.lookup("0000000000000000")
    finally:
        lookup.close()
    assert result is None


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))
    lookup = PdokCoordinateLookup()
    try:
        result = lookup.lookup("0363200000218780")
    finally:
        lookup.close()
    assert result is None


@respx.mock
def test_lookup_returns_none_on_malformed_wkt():
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json={"response": {"docs": [{"centroide_ll": "GARBAGE"}]}})
    )
    lookup = PdokCoordinateLookup()
    try:
        result = lookup.lookup("0363200000218780")
    finally:
        lookup.close()
    assert result is None


@respx.mock
def test_lookup_returns_none_on_missing_centroide_ll():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json={"response": {"docs": [{}]}}))
    lookup = PdokCoordinateLookup()
    try:
        result = lookup.lookup("0363200000218780")
    finally:
        lookup.close()
    assert result is None


@respx.mock
def test_lookup_sends_correct_query_params():
    route = respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_coords_response()))
    lookup = PdokCoordinateLookup()
    try:
        lookup.lookup("0363200000218780")
    finally:
        lookup.close()
    params = route.calls.last.request.url.params
    assert params["q"] == "nummeraanduiding_id:0363200000218780"
    assert params["fl"] == "centroide_ll"
    assert params["rows"] == "1"


# --- resolve_bag integration tests ---


def _bag_address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Keizersgracht",
        "huisnummer": 1,
        "postcode": "1015AA",
        "woonplaatsNaam": "Amsterdam",
        "nummeraanduidingIdentificatie": "0363200000218780",
    }
    base.update(overrides)
    return base


def _pending_listing(**overrides) -> Listing:
    defaults: dict = {
        "residence": None,
        "bag_status": BagStatus.PENDING,
        "title": "Canal house",
        "price": "€ 750.000 k.k.",
        "price_eur": 750_000,
        "status": ListingStatus.NEW,
        "postcode": "1015AA",
        "house_number": 1,
        "city": "Amsterdam",
    }
    defaults.update(overrides)
    return cast(Listing, ListingFactory(**defaults))


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_enriches_coordinates_on_new_residence():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_coords_response(4.893, 52.376)))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.residence is not None
    assert listing.residence.latitude == pytest.approx(52.376)
    assert listing.residence.longitude == pytest.approx(4.893)


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_skips_coordinates_when_residence_already_has_them():
    from scraping.tasks import resolve_bag

    existing = cast(
        Residence,
        ResidenceFactory(bag_id="0363200000218780", latitude=52.0, longitude=4.0),
    )
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    pdok_route = respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json=_pdok_coords_response(4.893, 52.376))
    )
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    existing.refresh_from_db()
    assert existing.latitude == pytest.approx(52.0)
    assert existing.longitude == pytest.approx(4.0)
    assert not pdok_route.called


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_continues_when_pdok_coordinates_fail():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence is not None
    assert listing.residence.latitude is None
    assert listing.residence.longitude is None


# --- backfill_coordinates management command tests ---


@pytest.mark.django_db
@respx.mock
def test_backfill_enriches_residences_missing_coordinates():
    from django.core.management import call_command

    r1 = cast(Residence, ResidenceFactory(bag_id="0363200000000001"))
    r2 = cast(Residence, ResidenceFactory(bag_id="0363200000000002"))
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_coords_response(4.5, 52.3)))

    out = StringIO()
    call_command("backfill_coordinates", "--batch-size=10", "--sleep=0", stdout=out)

    r1.refresh_from_db()
    r2.refresh_from_db()
    assert r1.latitude == pytest.approx(52.3)
    assert r1.longitude == pytest.approx(4.5)
    assert r2.latitude == pytest.approx(52.3)
    assert r2.longitude == pytest.approx(4.5)
    assert "Enriched 2" in out.getvalue()


@pytest.mark.django_db
@respx.mock
def test_backfill_skips_residences_with_coordinates():
    from django.core.management import call_command

    cast(Residence, ResidenceFactory(bag_id="0363200000000001", latitude=52.0, longitude=4.0))
    pdok_route = respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_coords_response()))

    out = StringIO()
    call_command("backfill_coordinates", "--batch-size=10", "--sleep=0", stdout=out)

    assert not pdok_route.called
    assert "All residences already have coordinates" in out.getvalue()


@pytest.mark.django_db
@respx.mock
def test_backfill_handles_pdok_failures_gracefully():
    from django.core.management import call_command

    cast(Residence, ResidenceFactory(bag_id="0363200000000001"))
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))

    out = StringIO()
    call_command("backfill_coordinates", "--batch-size=10", "--sleep=0", stdout=out)

    assert "failed 1" in out.getvalue()
