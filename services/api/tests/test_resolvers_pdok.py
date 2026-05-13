import httpx
import respx

from scraping.resolvers.pdok import PdokFuzzyResolver
from scraping.resolvers.types import AddressQuery, BagLookupSuccess

_TEST_PDOK_URL = "https://pdok.test/v3"


def _resolver() -> PdokFuzzyResolver:
    return PdokFuzzyResolver(base_url=_TEST_PDOK_URL)


def _suggest_response(doc_id: str = "adr-abc123", score: float = 12.5) -> dict:
    return {"response": {"docs": [{"type": "adres", "id": doc_id, "score": score}]}}


def _lookup_response(**overrides) -> dict:
    doc = {
        "nummeraanduiding_id": "0503200000016590",
        "straatnaam": "Cornelis de Wittstraat",
        "huisnummer": 46,
        "huisletter": None,
        "huisnummertoevoeging": None,
        "postcode": "2613GH",
        "woonplaatsnaam": "Delft",
    }
    doc.update(overrides)
    return {"response": {"docs": [doc]}}


@respx.mock
def test_pdok_resolver_succeeds_with_abbreviated_street():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json=_suggest_response()))
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(return_value=httpx.Response(200, json=_lookup_response()))
    with _resolver() as resolver:
        result = resolver.resolve(
            AddressQuery(postcode=None, house_number=46, street="Corn. de Wittstraat", city="Delft")
        )
    assert isinstance(result, BagLookupSuccess)
    assert result.bag_id == "0503200000016590"
    assert result.street == "Cornelis de Wittstraat"
    assert result.house_number == 46
    assert result.postcode == "2613GH"
    assert result.city == "Delft"


@respx.mock
def test_pdok_resolver_query_excludes_postcode():
    route = respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json=_suggest_response()))
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(return_value=httpx.Response(200, json=_lookup_response()))
    with _resolver() as resolver:
        resolver.resolve(
            AddressQuery(postcode="2613GG", house_number=46, street="Cornelis de Wittstraat", city="Delft")
        )
    q = route.calls.last.request.url.params["q"]
    assert "2613GG" not in q
    assert "Cornelis de Wittstraat" in q
    assert "46" in q
    assert "Delft" in q


@respx.mock
def test_pdok_resolver_returns_none_on_empty_suggest():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json={"response": {"docs": []}}))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Corn.", city="Delft"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_when_score_below_threshold():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json=_suggest_response(score=3.0)))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=1, street="Vague", city="City"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_empty_lookup():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json=_suggest_response()))
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(return_value=httpx.Response(200, json={"response": {"docs": []}}))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Corn.", city="Delft"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_suggest_500():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(500))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Klaterweg", city="Huizen"))
    assert result is None


@respx.mock
def test_pdok_resolver_returns_none_on_lookup_500():
    respx.get(f"{_TEST_PDOK_URL}/suggest").mock(return_value=httpx.Response(200, json=_suggest_response()))
    respx.get(f"{_TEST_PDOK_URL}/lookup").mock(return_value=httpx.Response(500))
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=46, street="Klaterweg", city="Huizen"))
    assert result is None


def test_pdok_resolver_returns_none_when_street_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street=None, city="Huizen"))
    assert result is None


def test_pdok_resolver_returns_none_when_city_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=9, street="Klaterweg", city=None))
    assert result is None


def test_pdok_resolver_returns_none_when_house_number_missing():
    with _resolver() as resolver:
        result = resolver.resolve(AddressQuery(postcode=None, house_number=None, street="Klaterweg", city="Huizen"))
    assert result is None
