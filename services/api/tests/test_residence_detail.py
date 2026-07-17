import pytest

from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
class TestResidenceDetail:
    def test_returns_full_shape_with_nested_listings(self, client):
        residence = ResidenceFactory(
            street="Martin Luther Kinglaan",
            house_number=129,
            bedroom_count=3,
            bathroom_count=2,
            surface_area_m2=120,
            build_year=1998,
            latitude=52.37,
            longitude=4.88,
        )
        listing = ListingFactory(residence=residence, image_url="https://example.com/a.jpg")

        response = client.get(f"/v1/residences/{residence.id}")  # ty: ignore[unresolved-attribute]

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == residence.id  # ty: ignore[unresolved-attribute]
        assert body["bag_id"] == residence.bag_id
        assert body["slug"] == "martin-luther-kinglaan-129"
        assert body["bedroom_count"] == 3
        assert body["bathroom_count"] == 2
        assert body["surface_area_m2"] == 120
        assert body["build_year"] == 1998
        assert body["foundation_risk_label"] is None
        assert len(body["listings"]) == 1
        assert body["listings"][0]["url"] == listing.url

    def test_unknown_id_returns_404(self, client):
        response = client.get("/v1/residences/999999")

        assert response.status_code == 404

    def test_ungeocoded_residence_is_returned(self, client):
        residence = ResidenceFactory(latitude=None, longitude=None)

        response = client.get(f"/v1/residences/{residence.id}")  # ty: ignore[unresolved-attribute]

        assert response.status_code == 200
        body = response.json()
        assert body["latitude"] is None
        assert body["longitude"] is None

    def test_query_count(self, client, django_assert_num_queries):
        residence = ResidenceFactory()
        ListingFactory.create_batch(3, residence=residence)

        with django_assert_num_queries(2):  # residence + listings prefetch
            client.get(f"/v1/residences/{residence.id}")  # ty: ignore[unresolved-attribute]
