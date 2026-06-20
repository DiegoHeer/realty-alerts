import httpx
import respx

from scraping.services.bestemmingsplan import BestemmingsplanLookup, BestemmingsplanResult

_PLANNEN_URL = "https://ruimte.omgevingswet.overheid.nl/ruimtelijke-plannen/api/opvragen/v4/plannen/_zoek"
_VLAKKEN_URL_PREFIX = "https://ruimte.omgevingswet.overheid.nl/ruimtelijke-plannen/api/opvragen/v4/plannen/"


def _plannen_response(plan_id: str = "NL.IMRO.0363.A0901BPSTD-VG01") -> dict:
    return {
        "_embedded": {
            "plannen": [{"id": plan_id, "naam": "Centrum", "planType": "bestemmingsplan", "regelStatus": "geldend"}]
        }
    }


def _bestemmingsvlakken_response(hoofdgroep: str = "Wonen", naam: str = "Wonen - 1") -> dict:
    return {"_embedded": {"bestemmingsvlakken": [{"naam": naam, "bestemmingshoofdgroep": hoofdgroep}]}}


@respx.mock
def test_lookup_returns_designation():
    respx.post(_PLANNEN_URL).mock(return_value=httpx.Response(200, json=_plannen_response()))
    respx.post(url__startswith=_VLAKKEN_URL_PREFIX).mock(
        return_value=httpx.Response(200, json=_bestemmingsvlakken_response())
    )

    with BestemmingsplanLookup(api_key="test-key") as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == BestemmingsplanResult(designation="Wonen")


@respx.mock
def test_lookup_returns_none_when_no_plans():
    respx.post(_PLANNEN_URL).mock(return_value=httpx.Response(200, json={"_embedded": {"plannen": []}}))

    with BestemmingsplanLookup(api_key="test-key") as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.post(_PLANNEN_URL).mock(return_value=httpx.Response(503))

    with BestemmingsplanLookup(api_key="test-key") as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_sends_api_key_header():
    route = respx.post(_PLANNEN_URL).mock(return_value=httpx.Response(200, json={"_embedded": {"plannen": []}}))

    with BestemmingsplanLookup(api_key="my-secret-key") as lookup:
        lookup.lookup(latitude=52.376, longitude=4.893)

    request = route.calls[0].request
    assert request.headers["x-api-key"] == "my-secret-key"
    assert request.headers["content-crs"] == "epsg:4326"
