import pytest
from datetime import UTC, datetime, timedelta

from scraping.models import Residence
from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
class TestResidenceList:
    endpoint = "/v1/residences"

    def test_returns_residences(self, client, user_headers):
        residence = ResidenceFactory()
        ListingFactory(residence=residence)

        response = client.get(self.endpoint, headers=user_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["bag_id"] == residence.bag_id

    def test_includes_nested_listings(self, client, user_headers):
        residence = ResidenceFactory()
        listing = ListingFactory(residence=residence)

        response = client.get(self.endpoint, headers=user_headers)

        result = response.json()[0]
        assert len(result["listings"]) == 1
        assert result["listings"][0]["url"] == listing.url

    def test_empty_database_returns_empty_list(self, client, user_headers):
        response = client.get(self.endpoint, headers=user_headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_filter_by_city(self, client, user_headers):
        ResidenceFactory(city="Amsterdam")
        ResidenceFactory(city="Rotterdam")

        response = client.get(self.endpoint, {"city": "amsterdam"}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["city"] == "Amsterdam"

    def test_filter_by_city_substring(self, client, user_headers):
        ResidenceFactory(city="Amsterdam")
        ResidenceFactory(city="Rotterdam")

        response = client.get(self.endpoint, {"city": "amster"}, headers=user_headers)

        assert len(response.json()) == 1

    def test_filter_by_neighbourhood(self, client, user_headers):
        ResidenceFactory(neighbourhood="Jordaan")
        ResidenceFactory(neighbourhood="De Pijp")

        response = client.get(self.endpoint, {"neighbourhood": "jordaan"}, headers=user_headers)

        assert len(response.json()) == 1

    def test_filter_by_district(self, client, user_headers):
        ResidenceFactory(district="Centrum")
        ResidenceFactory(district="Zuid")

        response = client.get(self.endpoint, {"district": "centrum"}, headers=user_headers)

        assert len(response.json()) == 1

    def test_filter_by_street(self, client, user_headers):
        r1 = ResidenceFactory(street="Keizersgracht")
        ResidenceFactory(street="Prinsengracht")

        response = client.get(self.endpoint, {"street": "keizers"}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == r1.id  # ty: ignore[unresolved-attribute]

    def test_filter_by_postcode(self, client, user_headers):
        ResidenceFactory(postcode="1015 CR")
        ResidenceFactory(postcode="3011 AA")

        response = client.get(self.endpoint, {"postcode": "1015 CR"}, headers=user_headers)

        assert len(response.json()) == 1

    def test_filter_by_postcode_case_insensitive(self, client, user_headers):
        ResidenceFactory(postcode="1015 CR")

        response = client.get(self.endpoint, {"postcode": "1015 cr"}, headers=user_headers)

        assert len(response.json()) == 1

    def test_filter_by_min_price(self, client, user_headers):
        ResidenceFactory(current_price_eur=200_000)
        ResidenceFactory(current_price_eur=500_000)

        response = client.get(self.endpoint, {"min_price": 300_000}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 500_000

    def test_filter_by_max_price(self, client, user_headers):
        ResidenceFactory(current_price_eur=200_000)
        ResidenceFactory(current_price_eur=500_000)

        response = client.get(self.endpoint, {"max_price": 300_000}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 200_000

    def test_filter_by_price_range(self, client, user_headers):
        ResidenceFactory(current_price_eur=100_000)
        ResidenceFactory(current_price_eur=300_000)
        ResidenceFactory(current_price_eur=600_000)

        response = client.get(self.endpoint, {"min_price": 200_000, "max_price": 400_000}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 300_000

    def test_filter_by_status(self, client, user_headers):
        ResidenceFactory(current_status="new")
        ResidenceFactory(current_status="sold")

        response = client.get(self.endpoint, {"status": "new"}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["current_status"] == "new"

    def test_multiple_filters_combined(self, client, user_headers):
        ResidenceFactory(city="Amsterdam", current_price_eur=300_000)
        ResidenceFactory(city="Amsterdam", current_price_eur=800_000)
        ResidenceFactory(city="Rotterdam", current_price_eur=300_000)

        response = client.get(self.endpoint, {"city": "amsterdam", "max_price": 500_000}, headers=user_headers)

        data = response.json()
        assert len(data) == 1
        assert data[0]["city"] == "Amsterdam"
        assert data[0]["current_price_eur"] == 300_000

    def test_default_pagination(self, client, user_headers):
        for _ in range(25):
            ResidenceFactory()

        response = client.get(self.endpoint, headers=user_headers)

        assert len(response.json()) == 20

    def test_custom_limit(self, client, user_headers):
        for _ in range(10):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 5}, headers=user_headers)

        assert len(response.json()) == 5

    def test_custom_offset(self, client, user_headers):
        for _ in range(10):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 5, "offset": 5}, headers=user_headers)

        assert len(response.json()) == 5

    def test_offset_beyond_results(self, client, user_headers):
        ResidenceFactory()

        response = client.get(self.endpoint, {"offset": 100}, headers=user_headers)

        assert response.json() == []

    def test_limit_clamped_to_max(self, client, user_headers):
        response = client.get(self.endpoint, {"limit": 200}, headers=user_headers)

        assert response.status_code == 422

    def test_limit_must_be_positive(self, client, user_headers):
        response = client.get(self.endpoint, {"limit": 0}, headers=user_headers)

        assert response.status_code == 422

    def test_offset_must_be_non_negative(self, client, user_headers):
        response = client.get(self.endpoint, {"offset": -1}, headers=user_headers)

        assert response.status_code == 422

    def test_ordered_by_newest_first(self, client, user_headers):
        r1 = ResidenceFactory()
        r2 = ResidenceFactory()

        now = datetime.now(UTC)
        Residence.objects.filter(pk=r1.pk).update(created_at=now - timedelta(seconds=10))  # ty: ignore[unresolved-attribute]
        Residence.objects.filter(pk=r2.pk).update(created_at=now)  # ty: ignore[unresolved-attribute]

        response = client.get(self.endpoint, headers=user_headers)

        ids = [r["id"] for r in response.json()]
        assert ids == [r2.id, r1.id]  # ty: ignore[unresolved-attribute]

    def test_no_n_plus_one_queries(self, client, user_headers, django_assert_num_queries):
        for _ in range(3):
            residence = ResidenceFactory()
            ListingFactory.create_batch(2, residence=residence)

        # 3 queries: 1 auth_user lookup (JWT), 1 residences, 1 prefetch listings
        with django_assert_num_queries(3):
            client.get(self.endpoint, headers=user_headers)
