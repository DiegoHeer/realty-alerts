import httpx
import respx

from scraping.services.bodemloket import BodemloketLookup, BodemloketResult

_ARCGIS_URL = "https://gis.gdngeoservices.nl/standalone/rest/services/blk_gdn/lks_blk_rd_v1/MapServer/0/query"


def _feature(status: str = "Onverdacht/Niet verontreinigd", outcome: str = "voldoende onderzocht") -> dict:
    return {"attributes": {"STATUS_OORD": status, "VERVOLG_WBB": outcome}}


@respx.mock
def test_lookup_returns_result_with_features():
    respx.get(_ARCGIS_URL).mock(
        return_value=httpx.Response(
            200, json={"features": [_feature(), _feature("niet ernstig, licht tot matig verontreinigd")]}
        )
    )

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == BodemloketResult(
        investigation_count=2,
        contamination_status="niet ernstig, licht tot matig verontreinigd",
        investigation_outcome="voldoende onderzocht",
    )


@respx.mock
def test_lookup_returns_zero_count_when_no_features():
    respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(200, json={"features": []}))

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result == BodemloketResult(investigation_count=0)


@respx.mock
def test_lookup_picks_worst_status_across_dossiers():
    respx.get(_ARCGIS_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    _feature("Onverdacht/Niet verontreinigd", "voldoende onderzocht"),
                    _feature("ernstig, geen risico's bepaald", "voldoende gesaneerd"),
                    _feature("niet ernstig, licht tot matig verontreinigd", "voldoende onderzocht"),
                ]
            },
        )
    )

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is not None
    assert result.investigation_count == 3
    assert result.contamination_status == "ernstig, geen risico's bepaald"
    assert result.investigation_outcome == "voldoende gesaneerd"


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(503))

    with BodemloketLookup() as lookup:
        result = lookup.lookup(latitude=52.376, longitude=4.893)

    assert result is None


@respx.mock
def test_lookup_sends_correct_spatial_params():
    route = respx.get(_ARCGIS_URL).mock(return_value=httpx.Response(200, json={"features": []}))

    with BodemloketLookup() as lookup:
        lookup.lookup(latitude=52.376, longitude=4.893)

    request = route.calls[0].request
    url = str(request.url)
    assert "geometryType=esriGeometryPoint" in url
    assert "inSR=4326" in url
    assert "spatialRel=esriSpatialRelIntersects" in url
    assert "returnGeometry=false" in url
    assert "STATUS_OORD" in url
    assert "VERVOLG_WBB" in url
