import httpx
import pytest
import respx
from datetime import UTC, datetime, timedelta

from scraping.models import City
from scraping.services.cbs import CBS_PRIMARY_YEAR, CBS_SECONDARY_YEAR, CBS_WFS_URL
from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory


@pytest.mark.django_db
class TestCityStats:
    def test_returns_city_stats(self, client):
        city = CityFactory(code="0518", name="'s-Gravenhage",
                           stats={"gemiddeldeWoningwaarde": 350}, stats_year=2024,
                           fetched_at=datetime.now(UTC))

        response = client.get(f"/v1/stats/cities/{city.code}")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "0518"
        assert data["stats"]["gemiddeldeWoningwaarde"] == 350
        assert data["stats_year"] == 2024

    def test_returns_404_for_unknown_city(self, client):
        response = client.get("/v1/stats/cities/9999")

        assert response.status_code == 404

    @respx.mock
    def test_fetches_when_stats_are_stale(self, client, settings):
        settings.CBS_CACHE_TTL_DAYS = 1
        city = CityFactory(code="0518", name="'s-Gravenhage",
                           geometry=[[[[4.2, 52.0], [4.4, 52.0], [4.4, 52.13], [4.2, 52.0]]]],
                           fetched_at=datetime.now(UTC) - timedelta(days=5))
        primary_url = CBS_WFS_URL.format(year=CBS_PRIMARY_YEAR)
        secondary_url = CBS_WFS_URL.format(year=CBS_SECONDARY_YEAR)
        respx.get(primary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection",
            "features": [{
                "properties": {"gemeentecode": "GM0518", "gemeentenaam": "'s-Gravenhage",
                               "gemiddeldeWoningwaarde": 400},
                "geometry": None,
            }],
        }))
        respx.get(secondary_url).mock(return_value=httpx.Response(200, json={
            "type": "FeatureCollection", "features": [],
        }))

        response = client.get("/v1/stats/cities/0518")

        assert response.status_code == 200
        assert response.json()["stats"]["gemiddeldeWoningwaarde"] == 400


@pytest.mark.django_db
class TestDistrictStats:
    def test_returns_districts_for_city(self, client):
        city = CityFactory(code="0518", fetched_at=datetime.now(UTC))
        DistrictFactory(code="WK051801", name="Scheveningen", city=city,
                        stats={"woz": 400}, stats_year=2024, fetched_at=datetime.now(UTC))
        DistrictFactory(code="WK051802", name="Laak", city=city,
                        stats={"woz": 300}, stats_year=2024, fetched_at=datetime.now(UTC))
        DistrictFactory(code="WK036301", city=CityFactory(code="0363"),
                        fetched_at=datetime.now(UTC))

        response = client.get("/v1/stats/districts", {"city": "0518"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        codes = {d["code"] for d in data}
        assert codes == {"WK051801", "WK051802"}

    def test_requires_city_param(self, client):
        response = client.get("/v1/stats/districts")

        assert response.status_code == 422

    def test_returns_404_for_unknown_city(self, client):
        response = client.get("/v1/stats/districts", {"city": "9999"})

        assert response.status_code == 404

    def test_excludes_geometry_by_default(self, client):
        city = CityFactory(code="0518", fetched_at=datetime.now(UTC))
        DistrictFactory(city=city, geometry=[[[[4.2, 52.0], [4.3, 52.1], [4.2, 52.0]]]],
                        fetched_at=datetime.now(UTC))

        response = client.get("/v1/stats/districts", {"city": "0518"})

        assert response.json()[0]["geometry"] is None

    def test_includes_geometry_when_requested(self, client):
        city = CityFactory(code="0518", fetched_at=datetime.now(UTC))
        DistrictFactory(city=city, geometry=[[[[4.2, 52.0], [4.3, 52.1], [4.2, 52.0]]]],
                        fetched_at=datetime.now(UTC))

        response = client.get("/v1/stats/districts", {"city": "0518", "include": "geometry"})

        assert response.json()[0]["geometry"] is not None


@pytest.mark.django_db
class TestNeighborhoodStats:
    def test_returns_neighborhoods_for_city(self, client):
        city = CityFactory(code="0518", fetched_at=datetime.now(UTC))
        district = DistrictFactory(city=city, fetched_at=datetime.now(UTC))
        NeighborhoodFactory(code="BU05180100", city=city, district=district,
                            stats={"woz": 380}, stats_year=2024, fetched_at=datetime.now(UTC))

        response = client.get("/v1/stats/neighborhoods", {"city": "0518"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "BU05180100"
        assert data[0]["district_code"] == district.code

    def test_requires_city_param(self, client):
        response = client.get("/v1/stats/neighborhoods")

        assert response.status_code == 422

    def test_returns_404_for_unknown_city(self, client):
        response = client.get("/v1/stats/neighborhoods", {"city": "9999"})

        assert response.status_code == 404
