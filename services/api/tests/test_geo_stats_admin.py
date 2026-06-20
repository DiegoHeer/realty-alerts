from typing import cast
from unittest.mock import patch

import pytest

from scraping.models import City, District, Neighborhood
from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory


@pytest.mark.django_db
class TestCityAdminActions:
    def test_fetch_geo_shapes_dispatches_tasks(self, admin_client):
        c1 = cast(City, CityFactory())
        c2 = cast(City, CityFactory())
        with patch("scraping.admin.fetch_city_geo_shape.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_geo_shapes", "_selected_action": [c1.pk, c2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(c1.pk)
        mock_delay.assert_any_call(c2.pk)

    def test_fetch_stats_dispatches_tasks(self, admin_client):
        c1 = cast(City, CityFactory())
        c2 = cast(City, CityFactory())
        with patch("scraping.admin.fetch_city_stats.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_stats", "_selected_action": [c1.pk, c2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(c1.pk)
        mock_delay.assert_any_call(c2.pk)


@pytest.mark.django_db
class TestDistrictAdminActions:
    def test_fetch_geo_shapes_dispatches_tasks(self, admin_client):
        d1 = cast(District, DistrictFactory())
        d2 = cast(District, DistrictFactory())
        with patch("scraping.admin.fetch_district_geo_shape.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_geo_shapes", "_selected_action": [d1.pk, d2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(d1.pk)
        mock_delay.assert_any_call(d2.pk)

    def test_fetch_stats_dispatches_tasks(self, admin_client):
        d1 = cast(District, DistrictFactory())
        d2 = cast(District, DistrictFactory())
        with patch("scraping.admin.fetch_district_stats.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_stats", "_selected_action": [d1.pk, d2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(d1.pk)
        mock_delay.assert_any_call(d2.pk)


@pytest.mark.django_db
class TestNeighborhoodAdminActions:
    def test_fetch_geo_shapes_dispatches_tasks(self, admin_client):
        n1 = cast(Neighborhood, NeighborhoodFactory())
        n2 = cast(Neighborhood, NeighborhoodFactory())
        with patch("scraping.admin.fetch_neighbourhood_geo_shape.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/neighborhood/",
                {"action": "fetch_geo_shapes", "_selected_action": [n1.pk, n2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(n1.pk)
        mock_delay.assert_any_call(n2.pk)

    def test_fetch_stats_dispatches_tasks(self, admin_client):
        n1 = cast(Neighborhood, NeighborhoodFactory())
        n2 = cast(Neighborhood, NeighborhoodFactory())
        with patch("scraping.admin.fetch_neighbourhood_stats.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/neighborhood/",
                {"action": "fetch_stats", "_selected_action": [n1.pk, n2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(n1.pk)
        mock_delay.assert_any_call(n2.pk)
