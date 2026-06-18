from typing import cast
from unittest.mock import patch

import pytest

from scraping.models import City, District, Neighborhood
from scraping.services import cbs as cbs_module
from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory

_SAMPLE_GEOMETRY = [[[4.0, 52.0], [5.0, 52.0], [5.0, 53.0], [4.0, 53.0], [4.0, 52.0]]]
_SAMPLE_STATS = {"AantalInwoners_5": 548320, "GemiddeldInkomenPerInwoner_67": 28.5}


@pytest.mark.django_db
class TestFetchCityGeoShape:
    def test_saves_geometry(self):
        from scraping.tasks import fetch_city_geo_shape

        city = cast(City, CityFactory(code="0518"))

        with patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=_SAMPLE_GEOMETRY) as mock_fetch:
            fetch_city_geo_shape(city.pk)

        mock_fetch.assert_called_once_with("gemeente_gegeneraliseerd", "GM0518")
        city.refresh_from_db()
        assert city.geometry == _SAMPLE_GEOMETRY
        assert city.geometry_fetched_at is not None

    def test_no_op_when_geometry_not_found(self):
        from scraping.tasks import fetch_city_geo_shape

        city = cast(City, CityFactory(code="9999"))

        with patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=None):
            fetch_city_geo_shape(city.pk)

        city.refresh_from_db()
        assert city.geometry is None
        assert city.geometry_fetched_at is None

    def test_no_op_when_city_deleted(self):
        from scraping.tasks import fetch_city_geo_shape

        fetch_city_geo_shape(999999)


@pytest.mark.django_db
class TestFetchDistrictGeoShape:
    def test_saves_geometry_with_bbox(self):
        from scraping.tasks import fetch_district_geo_shape

        city_geom = [[[4.0, 52.0], [5.0, 52.0], [5.0, 53.0], [4.0, 53.0], [4.0, 52.0]]]
        district = cast(District, DistrictFactory(code="WK051801", city__geometry=city_geom))

        with (
            patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=_SAMPLE_GEOMETRY) as mock_fetch,
            patch("scraping.tasks.cbs._bbox_from_geometries", return_value=(4.0, 52.0, 5.0, 53.0)) as mock_bbox,
        ):
            fetch_district_geo_shape(district.pk)

        mock_bbox.assert_called_once_with([city_geom])
        mock_fetch.assert_called_once_with("wijk_gegeneraliseerd", "WK051801", bbox=(4.0, 52.0, 5.0, 53.0))
        district.refresh_from_db()
        assert district.geometry == _SAMPLE_GEOMETRY
        assert district.geometry_fetched_at is not None

    def test_no_bbox_when_city_has_no_geometry(self):
        from scraping.tasks import fetch_district_geo_shape

        district = cast(District, DistrictFactory(code="WK051801", city__geometry=None))

        with patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=_SAMPLE_GEOMETRY) as mock_fetch:
            fetch_district_geo_shape(district.pk)

        mock_fetch.assert_called_once_with("wijk_gegeneraliseerd", "WK051801", bbox=None)

    def test_no_op_when_district_deleted(self):
        from scraping.tasks import fetch_district_geo_shape

        fetch_district_geo_shape(999999)


@pytest.mark.django_db
class TestFetchNeighbourhoodGeoShape:
    def test_saves_geometry_with_bbox(self):
        from scraping.tasks import fetch_neighbourhood_geo_shape

        city_geom = [[[4.0, 52.0], [5.0, 52.0], [5.0, 53.0], [4.0, 53.0], [4.0, 52.0]]]
        neighbourhood = cast(Neighborhood, NeighborhoodFactory(code="BU05180100", city__geometry=city_geom))

        with (
            patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=_SAMPLE_GEOMETRY) as mock_fetch,
            patch("scraping.tasks.cbs._bbox_from_geometries", return_value=(4.0, 52.0, 5.0, 53.0)) as mock_bbox,
        ):
            fetch_neighbourhood_geo_shape(neighbourhood.pk)

        mock_bbox.assert_called_once_with([city_geom])
        mock_fetch.assert_called_once_with("buurt_gegeneraliseerd", "BU05180100", bbox=(4.0, 52.0, 5.0, 53.0))
        neighbourhood.refresh_from_db()
        assert neighbourhood.geometry == _SAMPLE_GEOMETRY
        assert neighbourhood.geometry_fetched_at is not None

    def test_no_bbox_when_city_has_no_geometry(self):
        from scraping.tasks import fetch_neighbourhood_geo_shape

        neighbourhood = cast(Neighborhood, NeighborhoodFactory(code="BU05180100", city__geometry=None))

        with patch("scraping.tasks.cbs.fetch_entity_geometry", return_value=_SAMPLE_GEOMETRY) as mock_fetch:
            fetch_neighbourhood_geo_shape(neighbourhood.pk)

        mock_fetch.assert_called_once_with("buurt_gegeneraliseerd", "BU05180100", bbox=None)

    def test_no_op_when_neighbourhood_deleted(self):
        from scraping.tasks import fetch_neighbourhood_geo_shape

        fetch_neighbourhood_geo_shape(999999)


@pytest.mark.django_db
class TestFetchCityStats:
    def test_saves_stats(self):
        from scraping.tasks import fetch_city_stats

        city = cast(City, CityFactory(code="0518"))

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=_SAMPLE_STATS) as mock_fetch:
            fetch_city_stats(city.pk)

        mock_fetch.assert_called_once_with("GM0518")
        city.refresh_from_db()
        assert city.stats == _SAMPLE_STATS
        assert city.stats_year == cbs_module.CBS_ODATA_YEAR
        assert city.stats_fetched_at is not None

    def test_no_op_when_stats_not_found(self):
        from scraping.tasks import fetch_city_stats

        city = cast(City, CityFactory(code="9999"))

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=None):
            fetch_city_stats(city.pk)

        city.refresh_from_db()
        assert city.stats is None
        assert city.stats_fetched_at is None

    def test_no_op_when_city_deleted(self):
        from scraping.tasks import fetch_city_stats

        fetch_city_stats(999999)


@pytest.mark.django_db
class TestFetchDistrictStats:
    def test_saves_stats(self):
        from scraping.tasks import fetch_district_stats

        district = cast(District, DistrictFactory(code="WK051801"))

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=_SAMPLE_STATS) as mock_fetch:
            fetch_district_stats(district.pk)

        mock_fetch.assert_called_once_with("WK051801")
        district.refresh_from_db()
        assert district.stats == _SAMPLE_STATS
        assert district.stats_year == cbs_module.CBS_ODATA_YEAR
        assert district.stats_fetched_at is not None

    def test_no_op_when_stats_not_found(self):
        from scraping.tasks import fetch_district_stats

        district = cast(District, DistrictFactory())

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=None):
            fetch_district_stats(district.pk)

        district.refresh_from_db()
        assert district.stats is None
        assert district.stats_fetched_at is None

    def test_no_op_when_district_deleted(self):
        from scraping.tasks import fetch_district_stats

        fetch_district_stats(999999)


@pytest.mark.django_db
class TestFetchNeighbourhoodStats:
    def test_saves_stats(self):
        from scraping.tasks import fetch_neighbourhood_stats

        neighbourhood = cast(Neighborhood, NeighborhoodFactory(code="BU05180100"))

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=_SAMPLE_STATS) as mock_fetch:
            fetch_neighbourhood_stats(neighbourhood.pk)

        mock_fetch.assert_called_once_with("BU05180100")
        neighbourhood.refresh_from_db()
        assert neighbourhood.stats == _SAMPLE_STATS
        assert neighbourhood.stats_year == cbs_module.CBS_ODATA_YEAR
        assert neighbourhood.stats_fetched_at is not None

    def test_no_op_when_stats_not_found(self):
        from scraping.tasks import fetch_neighbourhood_stats

        neighbourhood = cast(Neighborhood, NeighborhoodFactory())

        with patch("scraping.tasks.cbs.fetch_entity_stats", return_value=None):
            fetch_neighbourhood_stats(neighbourhood.pk)

        neighbourhood.refresh_from_db()
        assert neighbourhood.stats is None
        assert neighbourhood.stats_fetched_at is None

    def test_no_op_when_neighbourhood_deleted(self):
        from scraping.tasks import fetch_neighbourhood_stats

        fetch_neighbourhood_stats(999999)
