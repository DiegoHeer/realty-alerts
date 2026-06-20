from __future__ import annotations

import httpx
import pytest
import respx

from scraping.services.cbs import (
    CBS_ODATA_BASE,
    bbox_from_geometries,
    _extract_geometry,
    _odata_get,
    _pdok_collection_url,
    fetch_all_cities,
    fetch_city_geometry,
    fetch_city_stats,
    fetch_district_geometry,
    fetch_district_stats,
    fetch_districts_for_city,
    fetch_neighbourhood_geometry,
    fetch_neighbourhood_stats,
    fetch_neighbourhoods_for_district,
)


class TestExtractGeometry:
    def test_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[4.123456789, 52.123456789], [4.2, 52.0], [4.3, 52.1], [4.123456789, 52.123456789]]],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert result[0][0][0] == [4.12346, 52.12346]

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]],
                [[[5.0, 53.0], [5.1, 53.0], [5.1, 53.1], [5.0, 53.0]]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 2

    def test_unsupported_type_returns_empty(self):
        assert _extract_geometry({"type": "Point", "coordinates": [4.0, 52.0]}) == []


class TestBboxFromGeometries:
    def test_computes_bbox_from_single_geometry(self):
        geometry = [[[[4.0, 52.0], [4.5, 52.0], [4.5, 52.5], [4.0, 52.5], [4.0, 52.0]]]]
        result = bbox_from_geometries([geometry])
        assert result == (4.0, 52.0, 4.5, 52.5)

    def test_computes_bbox_spanning_multiple_geometries(self):
        geo1 = [[[[4.0, 52.0], [4.5, 52.0], [4.5, 52.5], [4.0, 52.5], [4.0, 52.0]]]]
        geo2 = [[[[5.0, 53.0], [5.5, 53.0], [5.5, 53.5], [5.0, 53.5], [5.0, 53.0]]]]
        result = bbox_from_geometries([geo1, geo2])
        assert result == (4.0, 52.0, 5.5, 53.5)

    def test_returns_none_for_empty_list(self):
        assert bbox_from_geometries([]) is None

    def test_returns_none_for_empty_geometry(self):
        assert bbox_from_geometries([[]]) is None


class TestOdataGet:
    @respx.mock
    def test_returns_values(self):
        respx.get(f"{CBS_ODATA_BASE}/TypedDataSet").mock(
            return_value=httpx.Response(200, json={"value": [{"Key": "GM0518", "Val": 42}]})
        )
        result = _odata_get("TypedDataSet", filter="WijkenEnBuurten eq 'GM0518    '")
        assert len(result) == 1
        assert result[0]["Val"] == 42

    @respx.mock
    def test_returns_empty_on_no_results(self):
        respx.get(f"{CBS_ODATA_BASE}/TypedDataSet").mock(return_value=httpx.Response(200, json={"value": []}))
        result = _odata_get("TypedDataSet", filter="WijkenEnBuurten eq 'GM9999    '")
        assert result == []

    @respx.mock
    def test_raises_on_http_error(self):
        respx.get(f"{CBS_ODATA_BASE}/TypedDataSet").mock(return_value=httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            _odata_get("TypedDataSet", filter="test")


# --- Test helpers ---

_GEMEENTE_URL = _pdok_collection_url("gemeente_gegeneraliseerd")
_WIJK_URL = _pdok_collection_url("wijk_gegeneraliseerd")
_BUURT_URL = _pdok_collection_url("buurt_gegeneraliseerd")
_ODATA_WB_URL = f"{CBS_ODATA_BASE}/WijkenEnBuurten"
_ODATA_DS_URL = f"{CBS_ODATA_BASE}/TypedDataSet"

_SAMPLE_GEOM = {
    "type": "MultiPolygon",
    "coordinates": [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]],
}


def _pdok_gemeente_response(*cities):
    features = [
        {
            "type": "Feature",
            "properties": {"statcode": f"GM{code}", "statnaam": name},
            "geometry": _SAMPLE_GEOM,
        }
        for code, name in cities
    ]
    return {"type": "FeatureCollection", "features": features}


def _pdok_feature(statcode, *, geom=None):
    return {
        "type": "Feature",
        "properties": {"statcode": statcode, "statnaam": "Test", "gm_code": "GM0518"},
        "geometry": geom or _SAMPLE_GEOM,
    }


def _odata_wb_row(key, title):
    return {"Key": key.ljust(10), "Title": title.ljust(40)}


def _odata_stats_row(code, **stats):
    return {
        "ID": 0,
        "WijkenEnBuurten": code.ljust(10),
        "Gemeentenaam_1": "Test".ljust(40),
        "SoortRegio_2": "Gemeente".ljust(10),
        "Codering_3": code.ljust(10),
        "IndelingswijzigingGemeenteWijkBuurt_4": ".",
        "AantalInwoners_5": 100000,
        **stats,
    }


# --- Hierarchy tests ---


class TestFetchAllCities:
    @respx.mock
    def test_returns_code_and_name(self):
        respx.get(_GEMEENTE_URL).mock(
            return_value=httpx.Response(
                200, json=_pdok_gemeente_response(("0518", "'s-Gravenhage"), ("0363", "Amsterdam"))
            )
        )
        result = fetch_all_cities()
        assert len(result) == 2
        assert {"code": "0518", "name": "'s-Gravenhage"} in result
        assert {"code": "0363", "name": "Amsterdam"} in result

    @respx.mock
    def test_strips_gm_prefix(self):
        respx.get(_GEMEENTE_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_all_cities()
        assert result[0]["code"] == "0518"


class TestFetchDistrictsForCity:
    @respx.mock
    def test_returns_districts(self):
        respx.get(_ODATA_WB_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        _odata_wb_row("WK051801", "Wijk 01 Oostduinen"),
                        _odata_wb_row("WK051802", "Wijk 02 Belgisch Park"),
                    ]
                },
            )
        )
        result = fetch_districts_for_city("0518")
        assert len(result) == 2
        assert {"code": "WK051801", "name": "Wijk 01 Oostduinen"} in result

    @respx.mock
    def test_empty_result(self):
        respx.get(_ODATA_WB_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = fetch_districts_for_city("9999")
        assert result == []

    @respx.mock
    def test_filters_out_non_matching_prefix(self):
        respx.get(_ODATA_WB_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        _odata_wb_row("WK051801", "Correct"),
                        _odata_wb_row("WK105180", "Wrong prefix"),
                    ]
                },
            )
        )
        result = fetch_districts_for_city("0518")
        assert len(result) == 1
        assert result[0]["code"] == "WK051801"


class TestFetchNeighbourhoodsForDistrict:
    @respx.mock
    def test_returns_neighbourhoods(self):
        respx.get(_ODATA_WB_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        _odata_wb_row("BU05180100", "Schilderswijk-West"),
                        _odata_wb_row("BU05180101", "Schilderswijk-Oost"),
                    ]
                },
            )
        )
        result = fetch_neighbourhoods_for_district("WK051801")
        assert len(result) == 2
        assert {"code": "BU05180100", "name": "Schilderswijk-West"} in result

    @respx.mock
    def test_empty_result(self):
        respx.get(_ODATA_WB_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = fetch_neighbourhoods_for_district("WK999999")
        assert result == []


# --- Geometry tests ---


class TestFetchCityGeometry:
    @respx.mock
    def test_returns_geometry_for_requested_codes(self):
        respx.get(_GEMEENTE_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag"), ("0363", "Amsterdam")))
        )
        result = fetch_city_geometry(["0518"])
        assert "0518" in result
        assert "0363" not in result
        assert len(result["0518"]) == 1

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_GEMEENTE_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_city_geometry(["9999"])
        assert result == {}

    @respx.mock
    def test_batch_multiple_codes(self):
        respx.get(_GEMEENTE_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag"), ("0363", "Amsterdam")))
        )
        result = fetch_city_geometry(["0518", "0363"])
        assert len(result) == 2


class TestFetchDistrictGeometry:
    @respx.mock
    def test_returns_geometry_for_requested_codes(self):
        respx.get(_WIJK_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [_pdok_feature("WK051801"), _pdok_feature("WK051802")],
                    "links": [],
                },
            )
        )
        result = fetch_district_geometry(["WK051801"])
        assert "WK051801" in result
        assert "WK051802" not in result

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_WIJK_URL).mock(
            return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": [], "links": []})
        )
        result = fetch_district_geometry(["WK999999"])
        assert result == {}

    @respx.mock
    def test_passes_bbox_to_pdok(self):
        route = respx.get(_WIJK_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [_pdok_feature("WK051801")],
                    "links": [],
                },
            )
        )
        fetch_district_geometry(["WK051801"], bbox=(4.0, 52.0, 4.5, 52.5))
        assert "bbox" in str(route.calls[0].request.url)
        assert "4.0%2C52.0%2C4.5%2C52.5" in str(route.calls[0].request.url)


class TestFetchNeighbourhoodGeometry:
    @respx.mock
    def test_returns_geometry_for_requested_codes(self):
        respx.get(_BUURT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [_pdok_feature("BU05180100")],
                    "links": [],
                },
            )
        )
        result = fetch_neighbourhood_geometry(["BU05180100"])
        assert "BU05180100" in result

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_BUURT_URL).mock(
            return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": [], "links": []})
        )
        result = fetch_neighbourhood_geometry(["BU99999999"])
        assert result == {}

    @respx.mock
    def test_passes_bbox_to_pdok(self):
        route = respx.get(_BUURT_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "FeatureCollection",
                    "features": [_pdok_feature("BU05180100")],
                    "links": [],
                },
            )
        )
        fetch_neighbourhood_geometry(["BU05180100"], bbox=(4.0, 52.0, 4.5, 52.5))
        assert "bbox" in str(route.calls[0].request.url)
        assert "4.0%2C52.0%2C4.5%2C52.5" in str(route.calls[0].request.url)


# --- Stats tests ---


class TestFetchCityStats:
    @respx.mock
    def test_returns_stats_dict_keyed_by_code(self):
        respx.get(_ODATA_DS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"value": [_odata_stats_row("GM0518", GemiddeldeWOZWaardeVanWoningen_36=355)]},
            )
        )
        result = fetch_city_stats(["0518"])
        assert "GM0518" in result
        assert result["GM0518"]["GemiddeldeWOZWaardeVanWoningen_36"] == 355

    @respx.mock
    def test_excludes_metadata_keys(self):
        respx.get(_ODATA_DS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"value": [_odata_stats_row("GM0518", GemiddeldeWOZWaardeVanWoningen_36=355)]},
            )
        )
        stats = fetch_city_stats(["0518"])["GM0518"]
        assert "ID" not in stats
        assert "WijkenEnBuurten" not in stats
        assert "Gemeentenaam_1" not in stats
        assert "GemiddeldeWOZWaardeVanWoningen_36" in stats

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_ODATA_DS_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = fetch_city_stats(["9999"])
        assert result == {}

    @respx.mock
    def test_batch_multiple_codes(self):
        respx.get(_ODATA_DS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "value": [
                        _odata_stats_row("GM0518", GemiddeldeWOZWaardeVanWoningen_36=355),
                        _odata_stats_row("GM0363", GemiddeldeWOZWaardeVanWoningen_36=500),
                    ]
                },
            )
        )
        result = fetch_city_stats(["0518", "0363"])
        assert len(result) == 2
        assert result["GM0518"]["GemiddeldeWOZWaardeVanWoningen_36"] == 355
        assert result["GM0363"]["GemiddeldeWOZWaardeVanWoningen_36"] == 500


class TestFetchDistrictStats:
    @respx.mock
    def test_returns_stats_dict_keyed_by_code(self):
        respx.get(_ODATA_DS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"value": [_odata_stats_row("WK051801", GemiddeldeWOZWaardeVanWoningen_36=280)]},
            )
        )
        result = fetch_district_stats(["WK051801"])
        assert "WK051801" in result
        assert result["WK051801"]["GemiddeldeWOZWaardeVanWoningen_36"] == 280

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_ODATA_DS_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = fetch_district_stats(["WK999999"])
        assert result == {}


class TestFetchNeighbourhoodStats:
    @respx.mock
    def test_returns_stats_dict_keyed_by_code(self):
        respx.get(_ODATA_DS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"value": [_odata_stats_row("BU05180100", GemiddeldeWOZWaardeVanWoningen_36=200)]},
            )
        )
        result = fetch_neighbourhood_stats(["BU05180100"])
        assert "BU05180100" in result
        assert result["BU05180100"]["GemiddeldeWOZWaardeVanWoningen_36"] == 200

    @respx.mock
    def test_returns_empty_dict_for_unknown_code(self):
        respx.get(_ODATA_DS_URL).mock(return_value=httpx.Response(200, json={"value": []}))
        result = fetch_neighbourhood_stats(["BU99999999"])
        assert result == {}
