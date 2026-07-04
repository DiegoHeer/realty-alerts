import pytest

from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestResidenceListingFilters:
    endpoint = "/v1/residences"

    def test_min_bedrooms_inclusive(self, client):
        ResidenceFactory(bedroom_count=2)
        ResidenceFactory(bedroom_count=3)
        response = client.get(self.endpoint, {"min_bedrooms": 3})
        assert len(response.json()["items"]) == 1

    def test_min_bedrooms_excludes_null(self, client):
        ResidenceFactory(bedroom_count=None)
        response = client.get(self.endpoint, {"min_bedrooms": 1})
        assert response.json()["items"] == []

    def test_min_bathrooms_inclusive(self, client):
        ResidenceFactory(bathroom_count=1)
        ResidenceFactory(bathroom_count=2)
        response = client.get(self.endpoint, {"min_bathrooms": 2})
        assert len(response.json()["items"]) == 1

    def test_area_range_inclusive(self, client):
        ResidenceFactory(surface_area_m2=60)
        ResidenceFactory(surface_area_m2=100)
        ResidenceFactory(surface_area_m2=150)
        response = client.get(self.endpoint, {"min_area_m2": 70, "max_area_m2": 120})
        assert len(response.json()["items"]) == 1

    def test_area_excludes_null(self, client):
        ResidenceFactory(surface_area_m2=None)
        response = client.get(self.endpoint, {"min_area_m2": 1})
        assert response.json()["items"] == []

    def test_min_area_greater_than_max_is_empty(self, client):
        ResidenceFactory(surface_area_m2=100)
        response = client.get(self.endpoint, {"min_area_m2": 200, "max_area_m2": 50})
        assert response.json()["items"] == []

    def test_min_build_year_inclusive(self, client):
        ResidenceFactory(build_year=1980)
        ResidenceFactory(build_year=2000)
        response = client.get(self.endpoint, {"min_build_year": 1990})
        assert len(response.json()["items"]) == 1

    def test_min_build_year_excludes_null(self, client):
        ResidenceFactory(build_year=None)
        response = client.get(self.endpoint, {"min_build_year": 1900})
        assert response.json()["items"] == []

    def test_filters_and_combine(self, client):
        ResidenceFactory(bedroom_count=4, surface_area_m2=120)  # matches both
        ResidenceFactory(bedroom_count=4, surface_area_m2=50)  # fails area
        ResidenceFactory(bedroom_count=1, surface_area_m2=120)  # fails bedrooms
        response = client.get(self.endpoint, {"min_bedrooms": 3, "min_area_m2": 100})
        assert len(response.json()["items"]) == 1
