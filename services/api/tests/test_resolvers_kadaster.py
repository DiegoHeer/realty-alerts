import httpx
import pytest
import respx

from scraping.resolvers.kadaster import (
    KadasterConfig,
    KadasterPostcodeResolver,
    KadasterStreetCityResolver,
    resolve_addresses,
)
from scraping.resolvers.types import AddressQuery, BagLookupFailure, BagLookupSuccess

_TEST_BASE_URL = "https://bag.test/v2"


def _config() -> KadasterConfig:
    return KadasterConfig(api_key="test-key", base_url=_TEST_BASE_URL)


def _postcode_resolver() -> KadasterPostcodeResolver:
    return KadasterPostcodeResolver(_config())


def _street_city_resolver() -> KadasterStreetCityResolver:
    return KadasterStreetCityResolver(_config())


def _address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Klaterweg",
        "huisnummer": 9,
        "huisletter": "R",
        "huisnummertoevoeging": "A59",
        "postcode": "1271KE",
        "woonplaatsNaam": "Huizen",
        "nummeraanduidingIdentificatie": "0402200000084467",
    }
    base.update(overrides)
    return base


# --- resolve_addresses ---


def test_resolve_addresses_returns_single_result():
    result = resolve_addresses([_address()], house_letter="R", house_number_suffix="A59")
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"
    assert result.street == "Klaterweg"
    assert result.house_number == 9
    assert result.house_letter == "R"
    assert result.house_number_suffix == "A59"
    assert result.postcode == "1271KE"
    assert result.city == "Huizen"


def test_resolve_addresses_disambiguates_by_letter_and_suffix():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="R", huisnummertoevoeging="A59"),
    ]
    result = resolve_addresses(addresses, house_letter="R", house_number_suffix="A59")
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "002"


def test_resolve_addresses_disambiguates_by_absent_letter():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
    ]
    result = resolve_addresses(addresses, house_letter=None, house_number_suffix=None)
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "001"


def test_resolve_addresses_returns_ambiguous_when_multiple_match():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="A", huisnummertoevoeging=None),
    ]
    assert resolve_addresses(addresses, house_letter="A", house_number_suffix=None) is BagLookupFailure.AMBIGUOUS


def test_resolve_addresses_returns_ambiguous_when_none_match():
    addresses = [
        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
    ]
    assert resolve_addresses(addresses, house_letter="Z", house_number_suffix=None) is BagLookupFailure.AMBIGUOUS


# --- KadasterPostcodeResolver ---


def test_postcode_resolver_returns_none_when_postcode_missing():
    resolver = _postcode_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9))
    assert result is None


def test_postcode_resolver_returns_none_when_house_number_missing():
    resolver = _postcode_resolver()
    result = resolver.resolve(AddressQuery(postcode="1271KE", house_number=None))
    assert result is None


@respx.mock
def test_postcode_resolver_success():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        result = resolver.resolve(
            AddressQuery(postcode="1271 KE", house_number=9, house_letter="R", house_number_suffix="A59")
        )
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"


@respx.mock
def test_postcode_resolver_normalises_postcode():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271 ke", house_number=9))
    assert route.calls.last.request.url.params["postcode"] == "1271KE"


@respx.mock
def test_postcode_resolver_sends_optional_params():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9, house_letter="R", house_number_suffix="A59"))
    params = route.calls.last.request.url.params
    assert params["huisletter"] == "R"
    assert params["huisnummertoevoeging"] == "A59"


@respx.mock
def test_postcode_resolver_omits_optional_params_when_blank():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address(huisletter=None)]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))
    params = route.calls.last.request.url.params
    assert "huisletter" not in params
    assert "huisnummertoevoeging" not in params


@respx.mock
def test_postcode_resolver_returns_none_on_empty_results():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))
    with _postcode_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode="9999XX", house_number=1))
    assert result is None


@respx.mock
def test_postcode_resolver_returns_none_on_404():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(404))
    with _postcode_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode="9999XX", house_number=1))
    assert result is None


@respx.mock
def test_postcode_resolver_propagates_5xx():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    with _postcode_resolver() as resolver, pytest.raises(httpx.HTTPStatusError):
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))


@respx.mock
def test_postcode_resolver_sends_api_key_header():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _postcode_resolver() as resolver:
        resolver.resolve(AddressQuery(postcode="1271KE", house_number=9))
    assert route.calls.last.request.headers["X-Api-Key"] == "test-key"


# --- KadasterStreetCityResolver ---


def test_street_city_resolver_returns_none_when_street_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street=None, city="Huizen"))
    assert result is None


def test_street_city_resolver_returns_none_when_city_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city=None))
    assert result is None


def test_street_city_resolver_returns_none_when_house_number_missing():
    resolver = _street_city_resolver()
    result = resolver.resolve(AddressQuery(postcode=None, house_number=None, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_street_city_resolver_success():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )
    with _street_city_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen"))
    assert isinstance(result, BagLookupSuccess)
    params = route.calls.last.request.url.params
    assert params["openbareRuimteNaam"] == "Klaterweg"
    assert params["woonplaatsNaam"] == "Huizen"
    assert "postcode" not in params


@respx.mock
def test_street_city_resolver_returns_none_on_empty_results():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))
    with _street_city_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Nowhere", city="Faketown"))
    assert result is None


@respx.mock
def test_street_city_resolver_returns_none_on_404():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(404))
    with _street_city_resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_street_city_resolver_propagates_5xx():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    with _street_city_resolver() as resolver, pytest.raises(httpx.HTTPStatusError):
        resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city="Huizen"))
