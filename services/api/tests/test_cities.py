import pytest

from tests.factories import CityFactory


@pytest.mark.django_db
class TestListCities:
    endpoint = "/v1/cities"

    def test_returns_cached_cities(self, client):
        CityFactory(code="0518", name="'s-Gravenhage")
        CityFactory(code="0363", name="Amsterdam")

        response = client.get(self.endpoint)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        codes = {c["code"] for c in data}
        assert codes == {"0518", "0363"}

    def test_empty_db_returns_empty_list(self, client):
        response = client.get(self.endpoint)

        assert response.status_code == 200
        assert response.json() == []

    def test_no_auth_required(self, client):
        response = client.get(self.endpoint)

        assert response.status_code == 200

    def test_returns_code_and_name_only(self, client):
        CityFactory(code="0518", name="'s-Gravenhage", stats={"woz": 350})

        response = client.get(self.endpoint)

        item = response.json()[0]
        assert set(item.keys()) == {"code", "name"}
