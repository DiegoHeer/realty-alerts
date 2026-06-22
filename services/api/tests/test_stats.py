import pytest


from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory


@pytest.mark.django_db
class TestCityStats:
    def test_returns_city_stats(self, client, user_headers):
        CityFactory(
            code="0518",
            name="'s-Gravenhage",
            stats={"gemiddeldeWoningwaarde": 350},
            stats_year=2024,
        )

        response = client.get("/v1/stats/cities/0518", headers=user_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "0518"
        assert data["stats"]["gemiddeldeWoningwaarde"] == 350
        assert data["stats_year"] == 2024

    def test_returns_404_for_unknown_city(self, client, user_headers):
        response = client.get("/v1/stats/cities/9999", headers=user_headers)

        assert response.status_code == 404


@pytest.mark.django_db
class TestDistrictStats:
    def test_returns_districts_for_city(self, client, user_headers):
        city = CityFactory(code="0518")
        DistrictFactory(code="WK051801", name="Scheveningen", city=city, stats={"woz": 400}, stats_year=2024)
        DistrictFactory(code="WK051802", name="Laak", city=city, stats={"woz": 300}, stats_year=2024)
        DistrictFactory(code="WK036301", city=CityFactory(code="0363"))

        response = client.get("/v1/stats/districts", {"city": "0518"}, headers=user_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        codes = {d["code"] for d in data}
        assert codes == {"WK051801", "WK051802"}

    def test_requires_city_param(self, client, user_headers):
        response = client.get("/v1/stats/districts", headers=user_headers)

        assert response.status_code == 422

    def test_returns_404_for_unknown_city(self, client, user_headers):
        response = client.get("/v1/stats/districts", {"city": "9999"}, headers=user_headers)

        assert response.status_code == 404

    def test_excludes_geometry_by_default(self, client, user_headers):
        city = CityFactory(code="0518")
        DistrictFactory(city=city, geometry=[[[[4.2, 52.0], [4.3, 52.1], [4.2, 52.0]]]])

        response = client.get("/v1/stats/districts", {"city": "0518"}, headers=user_headers)

        assert response.json()[0]["geometry"] is None

    def test_includes_geometry_when_requested(self, client, user_headers):
        city = CityFactory(code="0518")
        DistrictFactory(city=city, geometry=[[[[4.2, 52.0], [4.3, 52.1], [4.2, 52.0]]]])

        response = client.get("/v1/stats/districts", {"city": "0518", "include": "geometry"}, headers=user_headers)

        assert response.json()[0]["geometry"] is not None


@pytest.mark.django_db
class TestNeighborhoodStats:
    def test_returns_neighborhoods_for_city(self, client, user_headers):
        city = CityFactory(code="0518")
        district = DistrictFactory(city=city)
        NeighborhoodFactory(code="BU05180100", city=city, district=district, stats={"woz": 380}, stats_year=2024)

        response = client.get("/v1/stats/neighborhoods", {"city": "0518"}, headers=user_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "BU05180100"
        assert data[0]["district_code"] == district.code

    def test_requires_city_param(self, client, user_headers):
        response = client.get("/v1/stats/neighborhoods", headers=user_headers)

        assert response.status_code == 422

    def test_returns_404_for_unknown_city(self, client, user_headers):
        response = client.get("/v1/stats/neighborhoods", {"city": "9999"}, headers=user_headers)

        assert response.status_code == 404
