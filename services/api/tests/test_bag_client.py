import httpx
import pytest
import respx

from scraping.bag_client import BagClient, BagLookupFailure, BagLookupSuccess

_TEST_BASE_URL = "https://bag.test/v2"


def _client() -> BagClient:
    return BagClient(api_key="test-key", base_url=_TEST_BASE_URL)


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


def test_lookup_returns_missing_address_when_postcode_blank():
    with _client() as client:
        result = client.lookup(postcode=None, house_number=9)
    assert result is BagLookupFailure.MISSING_ADDRESS


def test_lookup_returns_missing_address_when_house_number_none():
    with _client() as client:
        result = client.lookup(postcode="1271 KE", house_number=None)
    assert result is BagLookupFailure.MISSING_ADDRESS


@respx.mock
def test_lookup_success_returns_canonical_record():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        result = client.lookup(postcode="1271 KE", house_number=9, house_letter="R", house_number_suffix="A59")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"
    assert result.street == "Klaterweg"
    assert result.house_number == 9
    assert result.house_letter == "R"
    assert result.house_number_suffix == "A59"
    assert result.postcode == "1271KE"
    assert result.city == "Huizen"


@respx.mock
def test_lookup_strips_postcode_whitespace_and_passes_optional_params():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        client.lookup(postcode="1271 ke", house_number=9, house_letter="R", house_number_suffix="A59")

    sent = route.calls.last.request.url.params
    assert sent["postcode"] == "1271KE"
    assert sent["huisnummer"] == "9"
    assert sent["huisletter"] == "R"
    assert sent["huisnummertoevoeging"] == "A59"


@respx.mock
def test_lookup_omits_optional_params_when_blank():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address(huisletter=None)]}})
    )

    with _client() as client:
        client.lookup(postcode="1271KE", house_number=9)

    sent = route.calls.last.request.url.params
    assert "huisletter" not in sent
    assert "huisnummertoevoeging" not in sent


@respx.mock
def test_lookup_returns_no_match_on_empty_embedded():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))

    with _client() as client:
        result = client.lookup(postcode="9999XX", house_number=1)

    assert result is BagLookupFailure.NO_MATCH


@respx.mock
def test_lookup_returns_no_match_on_404():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(404, json={"detail": "not found"}))

    with _client() as client:
        result = client.lookup(postcode="9999XX", house_number=1)

    assert result is BagLookupFailure.NO_MATCH


@respx.mock
def test_lookup_returns_ambiguous_when_multiple_results():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="0402200000000001"),
                        _address(nummeraanduidingIdentificatie="0402200000000002"),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9)

    assert result is BagLookupFailure.AMBIGUOUS


@respx.mock
def test_lookup_propagates_5xx_for_celery_retry():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(503))

    with _client() as client, pytest.raises(httpx.HTTPStatusError):
        client.lookup(postcode="1271KE", house_number=9)


def test_lookup_returns_missing_address_when_house_number_none_even_with_street_city():
    with _client() as client:
        result = client.lookup(postcode=None, house_number=None, street="Klaterweg", city="Huizen")
    assert result is BagLookupFailure.MISSING_ADDRESS


def test_lookup_returns_missing_address_when_no_postcode_and_no_street():
    with _client() as client:
        result = client.lookup(postcode=None, house_number=9, street=None, city="Huizen")
    assert result is BagLookupFailure.MISSING_ADDRESS


def test_lookup_returns_missing_address_when_no_postcode_and_no_city():
    with _client() as client:
        result = client.lookup(postcode=None, house_number=9, street="Klaterweg", city=None)
    assert result is BagLookupFailure.MISSING_ADDRESS


@respx.mock
def test_lookup_falls_back_to_street_city_when_postcode_missing():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        result = client.lookup(
            postcode=None,
            house_number=9,
            house_letter="R",
            house_number_suffix="A59",
            street="Klaterweg",
            city="Huizen",
        )

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0402200000084467"
    sent = route.calls.last.request.url.params
    assert sent["openbareRuimteNaam"] == "Klaterweg"
    assert sent["woonplaatsNaam"] == "Huizen"
    assert sent["huisnummer"] == "9"
    assert sent["huisletter"] == "R"
    assert sent["huisnummertoevoeging"] == "A59"
    assert "postcode" not in sent


@respx.mock
def test_lookup_prefers_postcode_over_street_city_when_both_present():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        client.lookup(postcode="1271KE", house_number=9, street="Klaterweg", city="Huizen")

    sent = route.calls.last.request.url.params
    assert sent["postcode"] == "1271KE"
    assert "openbareRuimteNaam" not in sent
    assert "woonplaatsNaam" not in sent


@respx.mock
def test_lookup_street_city_fallback_returns_no_match_on_empty():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))

    with _client() as client:
        result = client.lookup(postcode=None, house_number=9, street="Klaterweg", city="Huizen")

    assert result is BagLookupFailure.NO_MATCH


@respx.mock
def test_lookup_street_city_fallback_returns_ambiguous_on_multiple():
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="0402200000000001"),
                        _address(nummeraanduidingIdentificatie="0402200000000002"),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode=None, house_number=9, street="Klaterweg", city="Huizen")

    assert result is BagLookupFailure.AMBIGUOUS


@respx.mock
def test_lookup_sends_api_key_header():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        client.lookup(postcode="1271KE", house_number=9)

    assert route.calls.last.request.headers["X-Api-Key"] == "test-key"
    assert route.calls.last.request.headers["Accept"] == "application/hal+json"
