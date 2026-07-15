import pytest
from django.db import connection

from tests.factories import ResidenceFactory

ENDPOINT = "/v1/residences/search"


def _requires_pg():
    """Skip trigram-specific assertions on the SQLite dev fallback (CI runs Postgres)."""
    if connection.vendor != "postgresql":
        pytest.skip("pg_trgm trigram search requires PostgreSQL")


@pytest.mark.django_db
class TestResidenceSearch:
    def test_short_query_returns_empty(self, client):
        ResidenceFactory(city="Amsterdam", street="Damrak")
        assert client.get(ENDPOINT, {"q": "a"}).json() == []

    def test_blank_query_returns_empty(self, client):
        ResidenceFactory(city="Amsterdam")
        assert client.get(ENDPOINT, {"q": "   "}).json() == []

    def test_matches_by_street(self, client):
        target = ResidenceFactory(street="Weena", city="Rotterdam", latitude=51.92, longitude=4.47)
        ResidenceFactory(street="Kalverstraat", city="Amsterdam")
        items = client.get(ENDPOINT, {"q": "Weena"}).json()
        assert items
        assert items[0]["id"] == target.id  # ty: ignore[unresolved-attribute]

    def test_matches_by_city_ranks_best_first(self, client):
        ResidenceFactory(city="Amsterdam", street="Damrak")
        ResidenceFactory(city="Rotterdam", street="Weena")
        items = client.get(ENDPOINT, {"q": "Amsterdam"}).json()
        assert items
        assert items[0]["city"] == "Amsterdam"

    def test_excludes_ungeocoded(self, client):
        ResidenceFactory(street="Weena", city="Rotterdam", latitude=None, longitude=None)
        assert client.get(ENDPOINT, {"q": "Weena"}).json() == []

    def test_limit_caps_results(self, client):
        for _ in range(12):
            ResidenceFactory(city="Amsterdam", street="Damrak")
        items = client.get(ENDPOINT, {"q": "Damrak", "limit": 5}).json()
        assert len(items) == 5

    def test_limit_out_of_range_422(self, client):
        assert client.get(ENDPOINT, {"q": "Damrak", "limit": 0}).status_code == 422

    def test_typo_tolerance(self, client):
        _requires_pg()
        ResidenceFactory(street="Kalverstraat", city="Amsterdam")
        items = client.get(ENDPOINT, {"q": "Kalverstrat"}).json()  # dropped an 'a'
        assert any(i["city"] == "Amsterdam" for i in items)

    def test_prefix_match(self, client):
        _requires_pg()
        ResidenceFactory(city="Amsterdam", street="Damrak")
        items = client.get(ENDPOINT, {"q": "amst"}).json()
        assert any(i["city"] == "Amsterdam" for i in items)
