import pytest

from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
class TestResidencePage:
    endpoint = "/v1/residences"

    def test_always_returns_envelope(self, client):
        ResidenceFactory()

        response = client.get(self.endpoint)

        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset", "has_more"}
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_stale_api_version_param_is_ignored(self, client):
        # Pre-split app builds still send ?api_version=2 during the deploy window.
        ResidenceFactory()

        response = client.get(self.endpoint, {"api_version": 2})

        assert response.status_code == 200
        assert set(response.json()) == {"items", "total", "limit", "offset", "has_more"}

    def test_total_ignores_pagination(self, client):
        for _ in range(5):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 2})

        body = response.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0
        assert body["has_more"] is True

    def test_has_more_false_on_last_page(self, client):
        for _ in range(3):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 2, "offset": 2})

        body = response.json()
        assert body["has_more"] is False
        assert len(body["items"]) == 1

    def test_no_n_plus_one(self, client, django_assert_num_queries):
        for _ in range(3):
            residence = ResidenceFactory()
            ListingFactory.create_batch(2, residence=residence)

        with django_assert_num_queries(2):  # count + main (cover image is an inlined subquery)
            client.get(self.endpoint)

    def test_limit_zero_count_only(self, client):
        for _ in range(4):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 0})

        body = response.json()
        assert body["items"] == []
        assert body["total"] == 4
        assert body["limit"] == 0
        assert body["has_more"] is True

    def test_limit_zero_total_zero_has_more_false(self, client):
        response = client.get(self.endpoint, {"limit": 0})

        body = response.json()
        assert body["total"] == 0
        assert body["has_more"] is False
