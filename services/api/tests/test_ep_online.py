from datetime import date

import httpx
import respx

from scraping.models import BuildingType, EnergyLabel
from scraping.services.ep_online import EpOnlineLookup

_EP_BASE_URL = "https://public.ep-online.nl/api/v5"
_EP_ADRES_URL = f"{_EP_BASE_URL}/PandEnergielabel/Adres"


def _ep_response(
    building_type: str = "rijwoning tussen",
    energy_label: str = "A+",
    valid_until: str = "2035-01-15",
) -> list[dict]:
    return [
        {
            "gebouwtype": building_type,
            "labelLetter": energy_label,
            "registratiedatum": "2025-03-10",
            "geldigTot": valid_until,
        }
    ]


# --- EpOnlineLookup unit tests ---


@respx.mock
def test_lookup_returns_building_details_on_success():
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=_ep_response("Appartement", "B", "2034-06-01")))
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
