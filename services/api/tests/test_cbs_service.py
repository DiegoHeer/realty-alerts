import httpx
import respx

from scraping.services import cbs

CBS_ODATA_URL = f"{cbs.CBS_ODATA_BASE}/TypedDataSet"


@respx.mock
def test_fetch_entity_stats_returns_stripped_stats():
    odata_key = "GM0518"
    respx.get(CBS_ODATA_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "value": [
                    {
                        "ID": 1,
                        "WijkenEnBuurten": "GM0518    ",
                        "Gemeentenaam_1": "  's-Gravenhage",
                        "SoortRegio_2": "Gemeente",
                        "Codering_3": "GM0518  ",
                        "IndelingswijzigingGemeenteWijkBuurt_4": None,
                        "AantalInwoners_5": 548320,
                        "GemiddeldInkomenPerInwoner_67": 28.5,
                    }
                ]
            },
        ),
    )

    result = cbs.fetch_entity_stats(odata_key)

    assert result == {"AantalInwoners_5": 548320, "GemiddeldInkomenPerInwoner_67": 28.5}


@respx.mock
def test_fetch_entity_stats_returns_none_when_no_match():
    respx.get(CBS_ODATA_URL).mock(
        return_value=httpx.Response(200, json={"value": []}),
    )

    result = cbs.fetch_entity_stats("GM9999")

    assert result is None


PDOK_GEMEENTE_URL = f"{cbs._PDOK_COLLECTIONS_URL}/gemeente_gegeneraliseerd/items"
PDOK_WIJK_URL = f"{cbs._PDOK_COLLECTIONS_URL}/wijk_gegeneraliseerd/items"


def _pdok_feature(statcode: str, geometry_type: str = "Polygon", coords: list | None = None) -> dict:
    default_coords = [[[4.0, 52.0], [5.0, 52.0], [5.0, 53.0], [4.0, 53.0], [4.0, 52.0]]]
    return {
        "properties": {"statcode": statcode},
        "geometry": {"type": geometry_type, "coordinates": coords or default_coords},
    }


@respx.mock
def test_fetch_entity_geometry_returns_geometry_for_matching_code():
    respx.get(PDOK_GEMEENTE_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "features": [
                    _pdok_feature("GM0518"),
                    _pdok_feature("GM0363"),
                ],
                "links": [],
            },
        ),
    )

    result = cbs.fetch_entity_geometry("gemeente_gegeneraliseerd", "GM0518")

    assert result is not None
    assert len(result) == 1
    assert result[0][0][0] == [4.0, 52.0]


@respx.mock
def test_fetch_entity_geometry_returns_none_when_no_match():
    respx.get(PDOK_GEMEENTE_URL).mock(
        return_value=httpx.Response(
            200,
            json={"features": [_pdok_feature("GM0363")], "links": []},
        ),
    )

    result = cbs.fetch_entity_geometry("gemeente_gegeneraliseerd", "GM9999")

    assert result is None


@respx.mock
def test_fetch_entity_geometry_passes_bbox():
    route = respx.get(PDOK_WIJK_URL).mock(
        return_value=httpx.Response(
            200,
            json={"features": [_pdok_feature("WK051801")], "links": []},
        ),
    )

    cbs.fetch_entity_geometry("wijk_gegeneraliseerd", "WK051801", bbox=(4.0, 52.0, 5.0, 53.0))

    assert "bbox" in str(route.calls[0].request.url)
