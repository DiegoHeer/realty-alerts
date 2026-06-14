import httpx
import pytest
import respx
from datetime import UTC, datetime, timedelta

from scraping.models import City
from scraping.services.cbs import CBS_PRIMARY_YEAR, _GEMEENTE_LABELPOINT_URL
from tests.factories import CityFactory


def _labelpoint_response(*cities):
    return httpx.Response(
        200,
        json={
            "type": "FeatureCollection",
            "features": [
                {
                    "properties": {"statcode": f"GM{code}", "statnaam": name, "jaarcode": CBS_PRIMARY_YEAR},
                    "geometry": {"type": "Point", "coordinates": [4.3, 52.08]},
                }
                for code, name in cities
            ],
        },
    )


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

    @respx.mock
    def test_fetches_from_cbs_when_db_empty(self, client):
        respx.get(_GEMEENTE_LABELPOINT_URL).mock(return_value=_labelpoint_response(("0518", "'s-Gravenhage")))

        response = client.get(self.endpoint)

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert City.objects.count() == 1

    @respx.mock
    def test_refreshes_when_stale(self, client, settings):
        settings.CBS_CACHE_TTL_DAYS = 1
        City.objects.create(code="0518", name="Old Name")
        City.objects.filter(code="0518").update(updated_at=datetime.now(UTC) - timedelta(days=5))
        respx.get(_GEMEENTE_LABELPOINT_URL).mock(return_value=_labelpoint_response(("0518", "New Name")))

        response = client.get(self.endpoint)

        assert response.status_code == 200
        assert response.json()[0]["name"] == "New Name"

    def test_no_auth_required(self, client):
        response = client.get(self.endpoint)

        assert response.status_code == 200

    def test_returns_code_and_name_only(self, client):
        CityFactory(code="0518", name="'s-Gravenhage", stats={"woz": 350})

        response = client.get(self.endpoint)

        item = response.json()[0]
        assert set(item.keys()) == {"code", "name"}
