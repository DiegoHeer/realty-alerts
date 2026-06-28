import pytest

from tests.factories import CityFactory, DistrictFactory, NeighborhoodFactory


SAMPLE_GEOMETRY = [[[[4.2, 52.0], [4.3, 52.0], [4.3, 52.1], [4.2, 52.0]]]]


@pytest.mark.django_db
class TestCityShapes:
    def test_returns_cities_with_geometry(self, client):
        CityFactory(code="0518", geometry=SAMPLE_GEOMETRY)

        response = client.get("/v1/shapes/cities")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "0518"
        assert data[0]["geometry"] == SAMPLE_GEOMETRY

    def test_excludes_cities_without_geometry(self, client):
        CityFactory(code="0518", geometry=SAMPLE_GEOMETRY)
        CityFactory(code="0363", geometry=None)

        response = client.get("/v1/shapes/cities")

        assert len(response.json()) == 1


@pytest.mark.django_db
class TestDistrictShapes:
    def test_returns_shapes_for_city(self, client):
        city = CityFactory(code="0518")
        DistrictFactory(city=city, geometry=SAMPLE_GEOMETRY)

        response = client.get("/v1/shapes/districts", {"city": "0518"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["geometry"] == SAMPLE_GEOMETRY

    def test_returns_404_for_unknown_city(self, client):
        response = client.get("/v1/shapes/districts", {"city": "9999"})

        assert response.status_code == 404

    def test_excludes_districts_without_geometry(self, client):
        city = CityFactory(code="0518")
        DistrictFactory(city=city, geometry=SAMPLE_GEOMETRY)
        DistrictFactory(city=city, geometry=None)

        response = client.get("/v1/shapes/districts", {"city": "0518"})

        assert len(response.json()) == 1


@pytest.mark.django_db
class TestNeighborhoodShapes:
    def test_returns_shapes_for_city(self, client):
        city = CityFactory(code="0518")
        district = DistrictFactory(city=city)
        NeighborhoodFactory(city=city, district=district, geometry=SAMPLE_GEOMETRY)

        response = client.get("/v1/shapes/neighborhoods", {"city": "0518"})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["geometry"] == SAMPLE_GEOMETRY
        assert data[0]["district_code"] == district.code

    def test_returns_404_for_unknown_city(self, client):
        response = client.get("/v1/shapes/neighborhoods", {"city": "9999"})

        assert response.status_code == 404
