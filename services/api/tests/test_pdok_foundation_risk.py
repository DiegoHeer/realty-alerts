import httpx
import pytest
import respx

from scraping.services.pdok_foundation_risk import (
    FoundationRiskResult,
    PdokFoundationRiskLookup,
)

_WFS_URL = "https://service.pdok.nl/rvo/indgebfunderingsproblematiek/wfs/v1_0"


def _wfs_response(legenda: str = "Kwetsbaar gebied - 40-60 %") -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "legenda": legenda,
                    "pc6": "1015AA",
                    "percvoor1970": "57.14",
                    "fgr": "Veengebied",
                },
                "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0]]]},
            }
        ],
    }


@respx.mock
def test_lookup_returns_result_on_success():
    respx.get(_WFS_URL).mock(return_value=httpx.Response(200, json=_wfs_response()))

    with PdokFoundationRiskLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == FoundationRiskResult(label="Kwetsbaar gebied - 40-60 %")


@respx.mock
def test_lookup_returns_none_on_empty_features():
    respx.get(_WFS_URL).mock(
        return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []})
    )

    with PdokFoundationRiskLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_WFS_URL).mock(return_value=httpx.Response(503))

    with PdokFoundationRiskLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_sends_correct_bbox_params():
    route = respx.get(_WFS_URL).mock(return_value=httpx.Response(200, json=_wfs_response()))

    with PdokFoundationRiskLookup() as lookup:
        lookup.lookup(latitude=52.376, longitude=4.893)

    request = route.calls[0].request
    assert "service=WFS" in str(request.url)
    assert "request=GetFeature" in str(request.url)
    assert "outputFormat=application%2Fjson" in str(request.url) or "outputFormat=application/json" in str(request.url)
