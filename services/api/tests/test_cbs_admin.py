from __future__ import annotations

from typing import cast
from unittest.mock import patch

import pytest
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME

from scraping.models import City, District, Neighborhood
from tests.factories import CityFactory, DistrictFactory


@pytest.mark.django_db
class TestSyncAllCities:
    def test_creates_cities(self, admin_client):
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            return_value=[
                {"code": "0518", "name": "'s-Gravenhage"},
                {"code": "0363", "name": "Amsterdam"},
            ],
        ):
            response = admin_client.post("/admin/scraping/city/sync-cities/")
        assert response.status_code == 302
        assert City.objects.count() == 2
        assert City.objects.get(code="0518").name == "'s-Gravenhage"

    def test_updates_existing_city(self, admin_client):
        CityFactory(code="0518", name="Old Name")
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            return_value=[{"code": "0518", "name": "'s-Gravenhage"}],
        ):
            admin_client.post("/admin/scraping/city/sync-cities/")
        assert City.objects.get(code="0518").name == "'s-Gravenhage"

    def test_reports_error(self, admin_client):
        with patch(
            "scraping.admin.cbs.fetch_all_cities",
            side_effect=RuntimeError("API down"),
        ):
            response = admin_client.post("/admin/scraping/city/sync-cities/")
        assert response.status_code == 302
        assert City.objects.count() == 0


@pytest.mark.django_db
class TestCityFetchDistricts:
    def test_creates_districts(self, admin_client):
        city = cast(City, CityFactory(code="0518"))
        with patch(
            "scraping.admin.cbs.fetch_districts_for_city",
            return_value=[
                {"code": "WK051801", "name": "Centrum"},
                {"code": "WK051802", "name": "Escamp"},
            ],
        ):
            admin_client.post(
                "/admin/scraping/city/",
                {"action": "fetch_districts", ACTION_CHECKBOX_NAME: [city.pk]},
            )
        assert District.objects.filter(city=city).count() == 2
        assert District.objects.get(code="WK051801").name == "Centrum"
        assert District.objects.get(code="WK051801").city == city


@pytest.mark.django_db
class TestDistrictFetchNeighbourhoods:
    def test_creates_neighbourhoods(self, admin_client):
        district = cast(District, DistrictFactory(code="WK051801"))
        with patch(
            "scraping.admin.cbs.fetch_neighbourhoods_for_district",
            return_value=[
                {"code": "BU05180100", "name": "Schilderswijk-West"},
                {"code": "BU05180101", "name": "Schilderswijk-Oost"},
            ],
        ):
            admin_client.post(
                "/admin/scraping/district/",
                {"action": "fetch_neighbourhoods", ACTION_CHECKBOX_NAME: [district.pk]},
            )
        assert Neighborhood.objects.filter(district=district).count() == 2
        nbh = Neighborhood.objects.get(code="BU05180100")
        assert nbh.name == "Schilderswijk-West"
        assert nbh.district == district
        assert nbh.city == district.city
