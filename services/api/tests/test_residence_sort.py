from datetime import UTC, datetime

import pytest

from scraping.models import Residence
from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestResidenceSort:
    endpoint = "/v1/residences"

    def test_default_is_newest(self, client):
        # Insertion order = ascending created_at; newest returns reverse.
        residences = [ResidenceFactory() for _ in range(3)]
        response = client.get(self.endpoint)
        ids = [r["id"] for r in response.json()["items"]]
        assert ids == [r.id for r in reversed(residences)]  # ty: ignore[unresolved-attribute]

    def test_sort_newest_explicit_matches_default(self, client):
        residences = [ResidenceFactory() for _ in range(3)]
        response = client.get(self.endpoint, {"sort": "newest"})
        ids = [r["id"] for r in response.json()["items"]]
        assert ids == [r.id for r in reversed(residences)]  # ty: ignore[unresolved-attribute]

    def test_sort_oldest_reverses_order(self, client):
        residences = [ResidenceFactory() for _ in range(3)]
        response = client.get(self.endpoint, {"sort": "oldest"})
        ids = [r["id"] for r in response.json()["items"]]
        assert ids == [r.id for r in residences]  # ty: ignore[unresolved-attribute]

    def test_oldest_id_tiebreaker_ascending(self, client):
        residences = [ResidenceFactory() for _ in range(5)]
        now = datetime.now(UTC)
        pks = [r.pk for r in residences]  # ty: ignore[unresolved-attribute]
        Residence.objects.filter(pk__in=pks).update(created_at=now)
        response = client.get(self.endpoint, {"sort": "oldest"})
        ids = [r["id"] for r in response.json()["items"]]
        assert ids == sorted(ids)

    def test_invalid_sort_returns_422(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint, {"sort": "cheapest"})
        assert response.status_code == 422


@pytest.mark.django_db
class TestSortDistance:
    endpoint = "/v1/residences"

    def test_orders_nearest_first(self, client):
        far = ResidenceFactory(latitude=52.3856, longitude=4.8841)  # ~2 km north
        near = ResidenceFactory(latitude=52.3686, longitude=4.8841)  # ~110 m north
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "sort": "distance"})
        ids = [item["id"] for item in response.json()["items"]]
        assert ids == [near.id, far.id]  # ty: ignore[unresolved-attribute]

    def test_distance_without_near_returns_422(self, client):
        response = client.get(self.endpoint, {"sort": "distance"})
        assert response.status_code == 422
