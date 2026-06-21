import httpx
import respx

from scraping.services.pdok_foundation_risk import (
    FoundationRiskResult,
    PdokFoundationRiskLookup,
)

_WFS_URL = "https://service.pdok.nl/rvo/indicatieve-aandachtsgebieden-funderingsproblematiek/wfs/v1_0"


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
def test_lookup_returns_result_with_none_label_on_empty_features():
    respx.get(_WFS_URL).mock(return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []}))

    with PdokFoundationRiskLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == FoundationRiskResult(label=None)


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
    url = str(request.url)
    assert "service=WFS" in url
    assert "request=GetFeature" in url
    assert "outputFormat=application%2Fjson" in url or "outputFormat=application/json" in url
    # WFS 2.0.0 EPSG:4326 requires lat,lon axis order (lat before lon)
    bbox_start = url.split("BBOX=")[1].split("%2C")
    first_coord = float(bbox_start[0])
    assert first_coord > 50, "BBOX should start with latitude (>50), not longitude (<10)"
