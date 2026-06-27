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
