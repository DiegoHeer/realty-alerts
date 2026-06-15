from __future__ import annotations

import httpx
import pytest
import respx

from scraping.services.cbs import (
    CBS_PRIMARY_YEAR,
    CBS_SECONDARY_YEAR,
    CBS_WFS_URL,
    _GEMEENTE_GEOMETRY_URL,
    _clean_stats,
    _extract_geometry,
    _merge_backfill,
    _wfs_get,
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


class TestCleanStats:
    def test_strips_sentinel_values(self):
        raw = {"woz": 350, "inkomen": -99997, "vermogen": -99998}
        result = _clean_stats(raw)
        assert result["woz"] == 350
        assert result["inkomen"] is None
        assert result["vermogen"] is None

    def test_strips_large_negative_sentinels(self):
        result = _clean_stats({"val": -99999998})
        assert result["val"] is None

    def test_preserves_valid_negative_values(self):
        result = _clean_stats({"val": -5, "other": -100})
        assert result["val"] == -5
        assert result["other"] == -100

    def test_preserves_non_numeric_values(self):
        result = _clean_stats({"name": "Amsterdam", "val": None})
        assert result["name"] == "Amsterdam"
        assert result["val"] is None


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


class TestMergeBackfill:
    def test_fills_none_from_secondary(self):
        primary = {"gemiddeldInkomenPerInwoner": None, "woz": 350}
        secondary = {"gemiddeldInkomenPerInwoner": 28000, "woz": 340}
        result = _merge_backfill(primary, secondary)
        assert result["gemiddeldInkomenPerInwoner"] == 28000
        assert result["woz"] == 350

    def test_no_secondary_returns_primary(self):
        primary = {"gemiddeldInkomenPerInwoner": None, "woz": 350}
        result = _merge_backfill(primary, None)
        assert result["gemiddeldInkomenPerInwoner"] is None

    def test_does_not_overwrite_existing_values(self):
        primary = {"gemiddeldInkomenPerInwoner": 30000}
        secondary = {"gemiddeldInkomenPerInwoner": 28000}
        result = _merge_backfill(primary, secondary)
        assert result["gemiddeldInkomenPerInwoner"] == 30000


class TestWfsGet:
    @respx.mock
    def test_returns_features(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        feature = {"type": "Feature", "properties": {"code": "WK001"}, "geometry": None}
        respx.get(url).mock(return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": [feature]}))
        result = _wfs_get("wijkenbuurten:wijken", cql_filter="gemeentecode='GM0518'")
        assert len(result) == 1
        assert result[0]["properties"]["code"] == "WK001"

    @respx.mock
    def test_retries_on_server_error(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        route = respx.get(url).mock(
            side_effect=[
                httpx.Response(500),
                httpx.Response(200, json={"type": "FeatureCollection", "features": []}),
            ]
        )
        result = _wfs_get("wijkenbuurten:wijken", max_retries=2, initial_delay=0.01)
        assert result == []
        assert route.call_count == 2

    @respx.mock
    def test_raises_after_max_retries(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(500))
        with pytest.raises(RuntimeError, match="CBS WFS request failed"):
            _wfs_get("wijkenbuurten:wijken", max_retries=2, initial_delay=0.01)


# --- Test helpers ---

def _pdok_gemeente_response(*cities):
    features = []
    for code, name in cities:
        features.append({
            "type": "Feature",
            "properties": {"statcode": f"GM{code}", "statnaam": name},
            "geometry": {"type": "MultiPolygon", "coordinates": [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]},
        })
    return {"type": "FeatureCollection", "features": features}


def _wfs_fc(*features):
    return httpx.Response(200, json={"type": "FeatureCollection", "features": list(features)})


def _wijk_feature(code, name, gm_code):
    return {
        "type": "Feature",
        "properties": {"wijkcode": code, "wijknaam": name, "gemeentecode": gm_code},
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


def _buurt_feature(code, name, wijk_code):
    return {
        "type": "Feature",
        "properties": {"buurtcode": code, "buurtnaam": name, "wijkcode": wijk_code},
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


def _gemeente_feature(code, **stats):
    props = {"gemeentecode": code, "gemeentenaam": "Test", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "MultiPolygon", "coordinates": [[[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]]},
    }


def _wijk_stats_feature(code, **stats):
    props = {"wijkcode": code, "wijknaam": "Test", "gemeentecode": "GM0518", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


def _buurt_stats_feature(code, **stats):
    props = {"buurtcode": code, "buurtnaam": "Test", "wijkcode": "WK051801", **stats}
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [[[4.0, 52.0], [4.1, 52.0], [4.1, 52.1], [4.0, 52.0]]]},
    }


# --- Hierarchy tests ---

class TestFetchAllCities:
    @respx.mock
    def test_returns_code_and_name(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "'s-Gravenhage"), ("0363", "Amsterdam")))
        )
        result = fetch_all_cities()
        assert len(result) == 2
        assert {"code": "0518", "name": "'s-Gravenhage"} in result
        assert {"code": "0363", "name": "Amsterdam"} in result

    @respx.mock
    def test_strips_gm_prefix(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_all_cities()
        assert result[0]["code"] == "0518"


class TestFetchDistrictsForCity:
    @respx.mock
    def test_returns_districts(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(
            _wijk_feature("WK051801", "Centrum", "GM0518"),
            _wijk_feature("WK051802", "Escamp", "GM0518"),
        ))
        result = fetch_districts_for_city("0518")
        assert len(result) == 2
        assert {"code": "WK051801", "name": "Centrum"} in result

    @respx.mock
    def test_empty_result(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        result = fetch_districts_for_city("9999")
        assert result == []


class TestFetchNeighbourhoodsForDistrict:
    @respx.mock
    def test_returns_neighbourhoods(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(
            _buurt_feature("BU05180100", "Schilderswijk-West", "WK051801"),
            _buurt_feature("BU05180101", "Schilderswijk-Oost", "WK051801"),
        ))
        result = fetch_neighbourhoods_for_district("WK051801")
        assert len(result) == 2
        assert {"code": "BU05180100", "name": "Schilderswijk-West"} in result


# --- Geometry tests ---

class TestFetchCityGeometry:
    @respx.mock
    def test_returns_geometry(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        result = fetch_city_geometry("0518")
        assert len(result) == 1
        assert len(result[0]) == 1

    @respx.mock
    def test_raises_for_unknown_city(self):
        respx.get(_GEMEENTE_GEOMETRY_URL).mock(
            return_value=httpx.Response(200, json=_pdok_gemeente_response(("0518", "Den Haag")))
        )
        with pytest.raises(ValueError, match="City 9999 not found"):
            fetch_city_geometry("9999")


class TestFetchDistrictGeometry:
    @respx.mock
    def test_returns_geometry(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(_wijk_feature("WK051801", "Centrum", "GM0518")))
        result = fetch_district_geometry("WK051801")
        assert len(result) == 1

    @respx.mock
    def test_raises_for_unknown_district(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="District WK999999 not found"):
            fetch_district_geometry("WK999999")


class TestFetchNeighbourhoodGeometry:
    @respx.mock
    def test_returns_geometry(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc(_buurt_feature("BU05180100", "Schilderswijk", "WK051801")))
        result = fetch_neighbourhood_geometry("BU05180100")
        assert len(result) == 1

    @respx.mock
    def test_raises_for_unknown_neighbourhood(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="Neighbourhood BU99999999 not found"):
            fetch_neighbourhood_geometry("BU99999999")


# --- Stats tests ---

class TestFetchCityStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_gemeente_feature("GM0518", gemiddeldeWoningwaarde=350)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_gemeente_feature("GM0518", gemiddeldeWoningwaarde=340)))
        stats, year = fetch_city_stats("0518")
        assert stats["gemiddeldeWoningwaarde"] == 350
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_backfills_from_secondary_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(
            _gemeente_feature("GM0518", gemiddeldInkomenPerInwoner=-99997, gemiddeldeWoningwaarde=350)
        ))
        respx.get(url_secondary).mock(return_value=_wfs_fc(
            _gemeente_feature("GM0518", gemiddeldInkomenPerInwoner=28000, gemiddeldeWoningwaarde=340)
        ))
        stats, _ = fetch_city_stats("0518")
        assert stats["gemiddeldInkomenPerInwoner"] == 28000
        assert stats["gemiddeldeWoningwaarde"] == 350

    @respx.mock
    def test_raises_for_unknown_city(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for city 9999"):
            fetch_city_stats("9999")


class TestFetchDistrictStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_wijk_stats_feature("WK051801", gemiddeldeWoningwaarde=280)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_wijk_stats_feature("WK051801", gemiddeldeWoningwaarde=270)))
        stats, year = fetch_district_stats("WK051801")
        assert stats["gemiddeldeWoningwaarde"] == 280
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_raises_for_unknown_district(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for district"):
            fetch_district_stats("WK999999")


class TestFetchNeighbourhoodStats:
    @respx.mock
    def test_returns_stats_and_year(self):
        url_primary = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        url_secondary = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(url_primary).mock(return_value=_wfs_fc(_buurt_stats_feature("BU05180100", gemiddeldeWoningwaarde=200)))
        respx.get(url_secondary).mock(return_value=_wfs_fc(_buurt_stats_feature("BU05180100", gemiddeldeWoningwaarde=190)))
        stats, year = fetch_neighbourhood_stats("BU05180100")
        assert stats["gemiddeldeWoningwaarde"] == 200
        assert year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_raises_for_unknown_neighbourhood(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=_wfs_fc())
        with pytest.raises(ValueError, match="No stats found for neighbourhood"):
            fetch_neighbourhood_stats("BU99999999")
