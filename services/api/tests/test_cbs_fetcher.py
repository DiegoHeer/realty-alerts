import httpx
import pytest
import respx
from datetime import UTC, datetime

from scraping.models import City, District, Neighborhood
from scraping.services.cbs import (
    CBS_PRIMARY_YEAR,
    CBS_SECONDARY_YEAR,
    CBS_WFS_URL,
    _clean_stats,
    _extract_geometry,
    _wfs_get,
    fetch_and_store_cities,
    fetch_and_store_districts,
)
from tests.factories import CityFactory


class TestCleanStats:
    def test_strips_sentinel_values(self):
        raw = {"woningvoorraad": 1200, "gemiddeldeWoningwaarde": -99997}
        result = _clean_stats(raw)
        assert result == {"woningvoorraad": 1200, "gemiddeldeWoningwaarde": None}

    def test_strips_all_sentinel_variants(self):
        raw = {"a": -99997, "b": -99998, "c": -99999998, "d": -99999997}
        result = _clean_stats(raw)
        assert all(v is None for v in result.values())

    def test_strips_large_negative_sentinels(self):
        raw = {"a": -99995}
        result = _clean_stats(raw)
        assert result == {"a": None}

    def test_preserves_valid_values(self):
        raw = {"a": 42, "b": 3.14, "c": "text", "d": None}
        result = _clean_stats(raw)
        assert result == {"a": 42, "b": 3.14, "c": "text", "d": None}

    def test_preserves_valid_negative_values(self):
        raw = {"a": -5, "b": -100}
        result = _clean_stats(raw)
        assert result == {"a": -5, "b": -100}


class TestExtractGeometry:
    def test_polygon(self):
        geom = {
            "type": "Polygon",
            "coordinates": [[[4.123456789, 52.123456789], [4.2, 52.2], [4.3, 52.1], [4.123456789, 52.123456789]]],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert result[0][0][0] == [4.12346, 52.12346]

    def test_multipolygon(self):
        geom = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[4.1, 52.1], [4.2, 52.2], [4.3, 52.1], [4.1, 52.1]]],
                [[[4.4, 52.4], [4.5, 52.5], [4.6, 52.4], [4.4, 52.4]]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 2

    def test_returns_empty_for_unsupported_type(self):
        geom = {"type": "Point", "coordinates": [4.1, 52.1]}
        result = _extract_geometry(geom)
        assert result == []

    def test_preserves_holes(self):
        geom = {
            "type": "Polygon",
            "coordinates": [
                [[4.1, 52.1], [4.2, 52.2], [4.3, 52.1], [4.1, 52.1]],
                [[4.15, 52.12], [4.18, 52.15], [4.22, 52.12], [4.15, 52.12]],
            ],
        }
        result = _extract_geometry(geom)
        assert len(result) == 1
        assert len(result[0]) == 2


@pytest.mark.django_db
class TestWfsGet:
    @respx.mock
    def test_returns_features_on_success(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [{"properties": {"gemeentecode": "GM0518"}, "geometry": None}],
        }))

        result = _wfs_get("wijkenbuurten:gemeenten", year=CBS_PRIMARY_YEAR)

        assert len(result) == 1
        assert result[0]["properties"]["gemeentecode"] == "GM0518"

    @respx.mock
    def test_retries_on_server_error(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        route = respx.get(url).mock(side_effect=[
            httpx.Response(500),
            httpx.Response(200, json={"type": "FeatureCollection", "features": []}),
        ])

        result = _wfs_get("wijkenbuurten:gemeenten", year=CBS_PRIMARY_YEAR, initial_delay=0.01)

        assert result == []
        assert route.call_count == 2

    @respx.mock
    def test_raises_after_max_retries(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(500))

        with pytest.raises(RuntimeError, match="CBS WFS request failed"):
            _wfs_get("wijkenbuurten:gemeenten", year=CBS_PRIMARY_YEAR, max_retries=2, initial_delay=0.01)


@pytest.mark.django_db
class TestFetchAndStoreCities:
    @respx.mock
    def test_creates_city_rows(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {"gemeentecode": "GM0518", "gemeentenaam": "'s-Gravenhage"},
                    "geometry": {"type": "Polygon", "coordinates": [[[4.2, 52.0], [4.4, 52.0], [4.4, 52.1], [4.2, 52.0]]]},
                },
                {
                    "properties": {"gemeentecode": "GM0363", "gemeentenaam": "Amsterdam"},
                    "geometry": {"type": "Polygon", "coordinates": [[[4.7, 52.3], [5.0, 52.3], [5.0, 52.4], [4.7, 52.3]]]},
                },
            ],
        }))

        fetch_and_store_cities()

        assert City.objects.count() == 2
        den_haag = City.objects.get(code="0518")
        assert den_haag.name == "'s-Gravenhage"
        assert den_haag.geometry is not None
        assert den_haag.stats is None
        assert den_haag.fetched_at is None

    @respx.mock
    def test_updates_existing_city(self):
        City.objects.create(code="0518", name="Old Name")
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [{
                "properties": {"gemeentecode": "GM0518", "gemeentenaam": "'s-Gravenhage"},
                "geometry": {"type": "Polygon", "coordinates": [[[4.2, 52.0], [4.4, 52.0], [4.4, 52.1], [4.2, 52.0]]]},
            }],
        }))

        fetch_and_store_cities()

        assert City.objects.count() == 1
        assert City.objects.get(code="0518").name == "'s-Gravenhage"

    @respx.mock
    def test_strips_gm_prefix_from_code(self):
        url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        respx.get(url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [{
                "properties": {"gemeentecode": "GM0518", "gemeentenaam": "Den Haag"},
                "geometry": None,
            }],
        }))

        fetch_and_store_cities()

        assert City.objects.filter(code="0518").exists()


def _gemeente_feature(code="GM0518", name="'s-Gravenhage", woz=350):
    return {
        "properties": {"gemeentecode": code, "gemeentenaam": name, "gemiddeldeWoningwaarde": woz},
        "geometry": None,
    }


def _wijk_feature(code="WK051801", name="Scheveningen", woz=400):
    return {
        "properties": {"wijkcode": code, "wijknaam": name, "gemiddeldeWoningwaarde": woz},
        "geometry": {"type": "Polygon", "coordinates": [[[4.2, 52.0], [4.3, 52.0], [4.3, 52.1], [4.2, 52.0]]]},
    }


def _buurt_feature(code="BU05180100", name="Schildersbuurt-West", wijk="WK051801", woz=380):
    return {
        "properties": {"buurtcode": code, "buurtnaam": name, "wijkcode": wijk, "gemiddeldeWoningwaarde": woz},
        "geometry": {"type": "Polygon", "coordinates": [[[4.25, 52.05], [4.28, 52.05], [4.28, 52.08], [4.25, 52.05]]]},
    }


_CITY_GEOMETRY = [[[[4.2, 52.0], [4.4, 52.0], [4.4, 52.13], [4.2, 52.0]]]]


@pytest.mark.django_db
class TestFetchAndStoreDistricts:
    @respx.mock
    def test_creates_districts_and_neighborhoods(self):
        city = CityFactory(code="0518", name="'s-Gravenhage", geometry=_CITY_GEOMETRY)
        primary_url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        secondary_url = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)

        respx.get(primary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [_gemeente_feature(), _wijk_feature(), _buurt_feature()],
        }))
        respx.get(secondary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection", "features": [],
        }))

        fetch_and_store_districts(city)

        assert District.objects.count() == 1
        district = District.objects.get(code="WK051801")
        assert district.name == "Scheveningen"
        assert district.city == city
        assert district.stats is not None
        assert district.geometry is not None
        assert district.fetched_at is not None

        assert Neighborhood.objects.count() == 1
        nb = Neighborhood.objects.get(code="BU05180100")
        assert nb.name == "Schildersbuurt-West"
        assert nb.district == district
        assert nb.city == city

    @respx.mock
    def test_updates_city_stats(self):
        city = CityFactory(code="0518", geometry=_CITY_GEOMETRY)
        primary_url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        secondary_url = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)

        respx.get(primary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [_gemeente_feature(woz=350)],
        }))
        respx.get(secondary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection", "features": [],
        }))

        fetch_and_store_districts(city)

        city.refresh_from_db()
        assert city.stats is not None
        assert city.stats["gemiddeldeWoningwaarde"] == 350
        assert city.fetched_at is not None
        assert city.stats_year == CBS_PRIMARY_YEAR

    @respx.mock
    def test_backfills_from_secondary_year(self):
        city = CityFactory(code="0518", geometry=_CITY_GEOMETRY)
        primary_url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        secondary_url = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)

        respx.get(primary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [
                {"properties": {"wijkcode": "WK051801", "wijknaam": "Scheveningen",
                                "gemiddeldInkomenPerInwoner": -99997},
                 "geometry": {"type": "Polygon", "coordinates": [[[4.2, 52.0], [4.3, 52.0], [4.3, 52.1], [4.2, 52.0]]]}},
            ],
        }))
        respx.get(secondary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [
                {"properties": {"wijkcode": "WK051801", "wijknaam": "Scheveningen",
                                "gemiddeldInkomenPerInwoner": 28},
                 "geometry": None},
            ],
        }))

        fetch_and_store_districts(city)

        district = District.objects.get(code="WK051801")
        assert district.stats["gemiddeldInkomenPerInwoner"] == 28

    @respx.mock
    def test_filters_by_city_code_prefix(self):
        city = CityFactory(code="0518", geometry=_CITY_GEOMETRY)
        primary_url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        secondary_url = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)

        respx.get(primary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [
                _wijk_feature(code="WK051801", name="Scheveningen"),
                _wijk_feature(code="WK036301", name="Centrum (Amsterdam)"),
            ],
        }))
        respx.get(secondary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection", "features": [],
        }))

        fetch_and_store_districts(city)

        assert District.objects.count() == 1
        assert District.objects.first().code == "WK051801"
