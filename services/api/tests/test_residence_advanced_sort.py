import pytest

from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestAdvancedSort:
    endpoint = "/v1/residences"

    def _ids(self, client, sort):
        body = client.get(self.endpoint, {"sort": sort, "limit": 100}).json()
        return [item["id"] for item in body["items"]]

    def test_price_asc_orders_cheapest_first(self, client):
        cheap = ResidenceFactory(current_price_eur=100_000)
        mid = ResidenceFactory(current_price_eur=300_000)
        expensive = ResidenceFactory(current_price_eur=900_000)
        assert self._ids(client, "price_asc") == [cheap.id, mid.id, expensive.id]  # ty: ignore[unresolved-attribute]

    def test_price_desc_orders_expensive_first(self, client):
        cheap = ResidenceFactory(current_price_eur=100_000)
        expensive = ResidenceFactory(current_price_eur=900_000)
        assert self._ids(client, "price_desc") == [expensive.id, cheap.id]  # ty: ignore[unresolved-attribute]

    def test_price_nulls_sort_last_in_both_directions(self, client):
        priced = ResidenceFactory(current_price_eur=200_000)
        unpriced = ResidenceFactory(current_price_eur=None)
        assert self._ids(client, "price_asc") == [priced.id, unpriced.id]  # ty: ignore[unresolved-attribute]
        assert self._ids(client, "price_desc") == [priced.id, unpriced.id]  # ty: ignore[unresolved-attribute]

    def test_area_asc_and_desc(self, client):
        small = ResidenceFactory(surface_area_m2=50)
        large = ResidenceFactory(surface_area_m2=150)
        assert self._ids(client, "area_asc") == [small.id, large.id]  # ty: ignore[unresolved-attribute]
        assert self._ids(client, "area_desc") == [large.id, small.id]  # ty: ignore[unresolved-attribute]

    def test_area_nulls_sort_last(self, client):
        sized = ResidenceFactory(surface_area_m2=80)
        unsized = ResidenceFactory(surface_area_m2=None)
        assert self._ids(client, "area_desc") == [sized.id, unsized.id]  # ty: ignore[unresolved-attribute]

    def test_price_per_m2_asc_best_value_first(self, client):
        # 100000/100 = 1000 ; 600000/100 = 6000
        good_value = ResidenceFactory(current_price_eur=100_000, surface_area_m2=100)
        poor_value = ResidenceFactory(current_price_eur=600_000, surface_area_m2=100)
        assert self._ids(client, "price_per_m2_asc") == [good_value.id, poor_value.id]  # ty: ignore[unresolved-attribute]

    def test_price_per_m2_nulls_last(self, client):
        valued = ResidenceFactory(current_price_eur=100_000, surface_area_m2=100)
        no_area = ResidenceFactory(current_price_eur=100_000, surface_area_m2=None)
        assert self._ids(client, "price_per_m2_asc") == [valued.id, no_area.id]  # ty: ignore[unresolved-attribute]

    def test_invalid_sort_rejected(self, client):
        response = client.get(self.endpoint, {"sort": "bananas"})
        assert response.status_code == 422
