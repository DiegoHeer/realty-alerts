import pytest

from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestResidenceFilters:
    endpoint = "/v1/residences"

    def test_deal_type_sale_is_default(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint)
        assert len(response.json()) == 1

    def test_deal_type_rent_returns_empty(self, client):
        ResidenceFactory()  # backfilled to sale
        response = client.get(self.endpoint, {"deal_type": "rent"})
        assert response.json() == []

    def test_deal_type_invalid_422(self, client):
        response = client.get(self.endpoint, {"deal_type": "lease"})
        assert response.status_code == 422

    def test_building_type_single(self, client):
        ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="detached")
        response = client.get(self.endpoint, {"building_type": "apartment"})
        data = response.json()
        assert len(data) == 1
        assert data[0]["building_type"] == "apartment"

    def test_building_type_or_repeated(self, client):
        ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="terraced")
        ResidenceFactory(building_type="detached")
        response = client.get(f"{self.endpoint}?building_type=apartment&building_type=terraced")
        assert len(response.json()) == 2

    def test_building_type_csv_fallback(self, client):
        ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="terraced")
        ResidenceFactory(building_type="detached")
        response = client.get(self.endpoint, {"building_type": "apartment,terraced"})
        assert len(response.json()) == 2

    def test_building_type_invalid_422(self, client):
        response = client.get(self.endpoint, {"building_type": "castle"})
        assert response.status_code == 422

    def test_building_type_null_excluded(self, client):
        ResidenceFactory(building_type=None)
        response = client.get(self.endpoint, {"building_type": "apartment"})
        assert response.json() == []

    def test_energy_label_or_repeated(self, client):
        ResidenceFactory(energy_label="A")
        ResidenceFactory(energy_label="B")
        ResidenceFactory(energy_label="G")
        response = client.get(f"{self.endpoint}?energy_label=A&energy_label=B")
        assert len(response.json()) == 2

    def test_energy_label_full_enum_value(self, client):
        ResidenceFactory(energy_label="A++++")
        ResidenceFactory(energy_label="C")
        response = client.get(self.endpoint, {"energy_label": "A++++"})  # urlencode escapes '+'
        assert len(response.json()) == 1

    def test_energy_label_invalid_422(self, client):
        response = client.get(self.endpoint, {"energy_label": "Z"})
        assert response.status_code == 422
