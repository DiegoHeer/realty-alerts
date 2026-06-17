from datetime import date

import httpx
import pytest
import respx

from scraping.models import BagStatus, BuildingType, EnergyLabel, Listing, ListingStatus, Residence
from scraping.services.ep_online import EpOnlineLookup
from tests.factories import ListingFactory, ResidenceFactory

_EP_BASE_URL = "https://public.ep-online.nl/api/v5"
_EP_ADRES_URL = f"{_EP_BASE_URL}/PandEnergielabel/Adres"


def _ep_response(
    building_type: str = "rijwoning tussen",
    energy_label: str = "A+",
    valid_until: str = "2035-01-15T00:00:00",
) -> list[dict]:
    return [
        {
            "Gebouwtype": building_type,
            "Energieklasse": energy_label,
            "Registratiedatum": "2025-03-10T00:00:00",
            "Geldig_tot": valid_until,
        }
    ]


# --- EpOnlineLookup unit tests ---


@respx.mock
def test_lookup_returns_building_details_on_success():
    ep_response = _ep_response("Appartement", "B", "2034-06-01T00:00:00")
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=ep_response))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is not None
    assert result.building_type == BuildingType.APARTMENT
    assert result.energy_label == EnergyLabel.B
    assert result.energy_label_valid_until == date(2034, 6, 1)


@respx.mock
def test_lookup_returns_none_on_empty_response():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=[]))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is None


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(503))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is None


@respx.mock
def test_lookup_sends_correct_params_and_auth_header():
    route = respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response()))
    with EpOnlineLookup(api_key="my-secret-key") as lookup:
        lookup.lookup(postcode="2514GL", house_number=42, house_letter="A", house_number_suffix="bis")
    request = route.calls.last.request
    assert request.headers["Authorization"] == "my-secret-key"
    params = request.url.params
    assert params["postcode"] == "2514GL"
    assert params["huisnummer"] == "42"
    assert params["huisletter"] == "A"
    assert params["huisnummertoevoeging"] == "bis"


@respx.mock
def test_lookup_omits_optional_params_when_none():
    route = respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response()))
    with EpOnlineLookup(api_key="test-key") as lookup:
        lookup.lookup(postcode="1015AA", house_number=1)
    params = route.calls.last.request.url.params
    assert "huisletter" not in params
    assert "huisnummertoevoeging" not in params


@respx.mock
def test_lookup_returns_none_building_type_for_unknown_string():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response("onbekend type", "A")))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is not None
    assert result.building_type is None
    assert result.energy_label == EnergyLabel.A


@respx.mock
def test_lookup_returns_none_energy_label_for_unknown_string():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response("Appartement", "X")))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is not None
    assert result.building_type == BuildingType.APARTMENT
    assert result.energy_label is None


@respx.mock
def test_lookup_handles_case_insensitive_building_type():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response("APPARTEMENT", "C")))
    with EpOnlineLookup(api_key="test-key") as lookup:
        result = lookup.lookup(postcode="1015AA", house_number=1)
    assert result is not None
    assert result.building_type == BuildingType.APARTMENT


# --- Integration test helpers ---

_BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"
_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_PDOK_FREE_URL = f"{_PDOK_BASE_URL}/free"


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


def _pdok_response() -> dict:
    return {
        "response": {"docs": [{"centroide_ll": "POINT(4.893 52.376)", "buurtnaam": "Centrum", "wijknaam": "Centrum"}]}
    }


def _pending_listing(**overrides) -> Listing:
    from typing import cast

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


# --- resolve_bag integration tests ---


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_enriches_building_details_on_new_residence(settings):
    from scraping.tasks import resolve_bag

    settings.EP_ONLINE_API_KEY = "test-key"
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_response()))
    ep_response = _ep_response("Appartement", "B", "2034-06-01T00:00:00")
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=ep_response))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.residence is not None
    assert listing.residence.building_type == BuildingType.APARTMENT
    assert listing.residence.energy_label == EnergyLabel.B
    assert listing.residence.energy_label_valid_until == date(2034, 6, 1)


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_skips_ep_online_when_building_type_already_set(settings):
    from typing import cast

    from scraping.tasks import resolve_bag

    settings.EP_ONLINE_API_KEY = "test-key"
    existing = cast(
        Residence,
        ResidenceFactory(
            bag_id="0363200000218780",
            latitude=52.0,
            longitude=4.0,
            neighbourhood="Centrum",
            district="Centrum",
            building_type=BuildingType.DETACHED,
        ),
    )
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    ep_route = respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response("Appartement", "A")))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    existing.refresh_from_db()
    assert existing.building_type == BuildingType.DETACHED
    assert not ep_route.called


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_continues_when_ep_online_fails(settings):
    from scraping.tasks import resolve_bag

    settings.EP_ONLINE_API_KEY = "test-key"
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_response()))
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(503))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence is not None
    assert listing.residence.building_type is None
