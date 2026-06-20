import httpx
import respx

from scraping.services.bodemloket import BodemloketLookup, BodemloketResult

_ARCGIS_URL = "https://www.gdngeoservices.nl/arcgis/rest/services/blk/lks_blk_rd/MapServer/1/query"


@respx.mock
def test_lookup_returns_count_on_success():
    respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(200, json={"count": 2}))

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == BodemloketResult(wbb_count=2)


@respx.mock
def test_lookup_returns_zero_count_when_no_locations():
    respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(200, json={"count": 0}))

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == BodemloketResult(wbb_count=0)


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(503))

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_sends_correct_spatial_params():
    route = respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(200, json={"count": 0}))

    with BodemloketLookup() as lookup:
        lookup.lookup(latitude=52.376, longitude=4.893)

    request = route.calls[0].request
    assert "geometryType=esriGeometryPoint" in str(request.url)
    assert "inSR=4326" in str(request.url)
    assert "spatialRel=esriSpatialRelIntersects" in str(request.url)
    assert "returnCountOnly=true" in str(request.url)
