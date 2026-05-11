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


@respx.mock
def test_lookup_sends_api_key_header():
    route = respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_address()]}})
    )

    with _client() as client:
        client.lookup(postcode="1271KE", house_number=9)

    assert route.calls.last.request.headers["X-Api-Key"] == "test-key"
    assert route.calls.last.request.headers["Accept"] == "application/hal+json"


# --- Disambiguation tests ---
# When the API returns multiple results (e.g. postcode+huisnummer matches several
# variants with/without house letter or suffix), the client must try to narrow
# to exactly one exact match before giving up with AMBIGUOUS.


@respx.mock
def test_lookup_disambiguates_by_absent_house_letter():
    """Kauwerspad 10 scenario: API returns the plain address and the 'B' variant;
    input has no letter so the plain one should be returned."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(
                            nummeraanduidingIdentificatie="0479200000024012", huisletter=None, huisnummertoevoeging=None
                        ),
                        _address(
                            nummeraanduidingIdentificatie="0479200000016659", huisletter="B", huisnummertoevoeging=None
                        ),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1506HC", house_number=10)

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0479200000024012"
    assert result.house_letter is None


@respx.mock
def test_lookup_disambiguates_by_house_letter_value():
    """Input specifies letter 'B'; API returns 'A' and 'B' variants; should pick 'B'."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="002", huisletter="B", huisnummertoevoeging=None),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9, house_letter="B")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "002"
    assert result.house_letter == "B"


@respx.mock
def test_lookup_disambiguates_by_suffix():
    """Input specifies suffix '2'; API returns '1' and '2' variants; should pick '2'."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging="1"),
                        _address(nummeraanduidingIdentificatie="002", huisletter=None, huisnummertoevoeging="2"),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9, house_number_suffix="2")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "002"
    assert result.house_number_suffix == "2"


@respx.mock
def test_lookup_disambiguates_by_letter_and_suffix():
    """Input specifies letter 'A' and suffix '1'; API returns three variants; should pick the one matching both."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter=None, huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="002", huisletter="A", huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="003", huisletter="A", huisnummertoevoeging="1"),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9, house_letter="A", house_number_suffix="1")

    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "003"


@respx.mock
def test_lookup_still_ambiguous_when_multiple_results_match():
    """Disambiguation finds 2+ matches (truly ambiguous) → still returns AMBIGUOUS."""
    respx.get(f"{_TEST_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _address(nummeraanduidingIdentificatie="001", huisletter="A", huisnummertoevoeging=None),
                        _address(nummeraanduidingIdentificatie="002", huisletter="A", huisnummertoevoeging=None),
                    ]
                }
            },
        )
    )

    with _client() as client:
        result = client.lookup(postcode="1271KE", house_number=9, house_letter="A")

    assert result is BagLookupFailure.AMBIGUOUS
