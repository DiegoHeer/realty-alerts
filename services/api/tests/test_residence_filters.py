import pytest
from datetime import UTC, datetime

from scraping.models import Residence
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

    def test_bbox_includes_point_inside(self, client):
        ResidenceFactory(latitude=52.08, longitude=4.29)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert len(response.json()) == 1

    def test_bbox_excludes_point_outside(self, client):
        ResidenceFactory(latitude=53.0, longitude=5.0)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert response.json() == []

    def test_bbox_excludes_null_coordinates(self, client):
        ResidenceFactory(latitude=None, longitude=None)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert response.json() == []

    def test_bbox_inverted_returns_empty(self, client):
        ResidenceFactory(latitude=52.08, longitude=4.29)
        response = client.get(self.endpoint, {"bbox": "4.32,52.10,4.26,52.06"})
        assert response.json() == []

    def test_bbox_malformed_422(self, client):
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32"})
        assert response.status_code == 422

    def test_bbox_out_of_range_422(self, client):
        response = client.get(self.endpoint, {"bbox": "4.26,99.0,4.32,100.0"})
        assert response.status_code == 422

    def test_min_price_above_max_price_returns_empty(self, client):
        ResidenceFactory(current_price_eur=300_000)
        response = client.get(self.endpoint, {"min_price": 500_000, "max_price": 400_000})
        assert response.json() == []

    def test_default_order_id_tiebreaker(self, client):
        r1 = ResidenceFactory()
        r2 = ResidenceFactory()
        now = datetime.now(UTC)
        Residence.objects.filter(pk__in=[r1.pk, r2.pk]).update(created_at=now)  # ty: ignore[unresolved-attribute]
        response = client.get(self.endpoint)
        ids = [r["id"] for r in response.json()]
        assert ids == [r2.id, r1.id]  # ty: ignore[unresolved-attribute]
