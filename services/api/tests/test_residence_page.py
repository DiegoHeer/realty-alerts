import pytest

from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
class TestResidencePage:
    endpoint = "/v1/residences"

    def test_legacy_absent_returns_bare_array(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_v2_query_param_returns_envelope(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint, {"api_version": 2})
        body = response.json()
        assert set(body) == {"items", "total", "limit", "offset", "has_more"}
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_v2_header_returns_envelope(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint, headers={"X-API-Version": "2"})
        assert isinstance(response.json(), dict)

    def test_query_param_wins_over_header(self, client):
        ResidenceFactory()
        response = client.get(f"{self.endpoint}?api_version=1", headers={"X-API-Version": "2"})
        assert isinstance(response.json(), list)

    def test_total_ignores_pagination(self, client):
        for _ in range(5):
            ResidenceFactory()
        response = client.get(self.endpoint, {"api_version": 2, "limit": 2})
        body = response.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0
        assert body["has_more"] is True

    def test_has_more_false_on_last_page(self, client):
        for _ in range(3):
            ResidenceFactory()
        response = client.get(self.endpoint, {"api_version": 2, "limit": 2, "offset": 2})
        body = response.json()
        assert body["has_more"] is False
        assert len(body["items"]) == 1

    def test_v2_no_n_plus_one(self, client, django_assert_num_queries):
        for _ in range(3):
            residence = ResidenceFactory()
            ListingFactory.create_batch(2, residence=residence)
        with django_assert_num_queries(3):  # count + residences + prefetch
            client.get(self.endpoint, {"api_version": 2})
