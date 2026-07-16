import pytest
from datetime import UTC, datetime, timedelta

from scraping.models import BagStatus, Residence
from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
class TestResidenceList:
    endpoint = "/v1/residences"

    def test_returns_residences(self, client):
        residence = ResidenceFactory(street="Martin Luther Kinglaan", house_number=129)
        ListingFactory(residence=residence)

        response = client.get(self.endpoint)

        assert response.status_code == 200
        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["id"] == residence.id  # ty: ignore[unresolved-attribute]
        assert data[0]["slug"] == "martin-luther-kinglaan-129"

    def test_empty_database_returns_empty_list(self, client):
        response = client.get(self.endpoint)

        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_filter_by_city(self, client):
        ResidenceFactory(city="Amsterdam")
        ResidenceFactory(city="Rotterdam")

        response = client.get(self.endpoint, {"city": "amsterdam"})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["city"] == "Amsterdam"

    def test_filter_by_city_substring(self, client):
        ResidenceFactory(city="Amsterdam")
        ResidenceFactory(city="Rotterdam")

        response = client.get(self.endpoint, {"city": "amster"})

        assert len(response.json()["items"]) == 1

    def test_filter_by_neighbourhood(self, client):
        ResidenceFactory(neighbourhood="Jordaan")
        ResidenceFactory(neighbourhood="De Pijp")

        response = client.get(self.endpoint, {"neighbourhood": "jordaan"})

        assert len(response.json()["items"]) == 1

    def test_filter_by_district(self, client):
        ResidenceFactory(district="Centrum")
        ResidenceFactory(district="Zuid")

        response = client.get(self.endpoint, {"district": "centrum"})

        assert len(response.json()["items"]) == 1

    def test_filter_by_street(self, client):
        r1 = ResidenceFactory(street="Keizersgracht")
        ResidenceFactory(street="Prinsengracht")

        response = client.get(self.endpoint, {"street": "keizers"})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["id"] == r1.id  # ty: ignore[unresolved-attribute]

    def test_filter_by_postcode(self, client):
        ResidenceFactory(postcode="1015 CR")
        ResidenceFactory(postcode="3011 AA")

        response = client.get(self.endpoint, {"postcode": "1015 CR"})

        assert len(response.json()["items"]) == 1

    def test_filter_by_postcode_case_insensitive(self, client):
        ResidenceFactory(postcode="1015 CR")

        response = client.get(self.endpoint, {"postcode": "1015 cr"})

        assert len(response.json()["items"]) == 1

    def test_filter_by_min_price(self, client):
        ResidenceFactory(current_price_eur=200_000)
        ResidenceFactory(current_price_eur=500_000)

        response = client.get(self.endpoint, {"min_price": 300_000})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 500_000

    def test_filter_by_max_price(self, client):
        ResidenceFactory(current_price_eur=200_000)
        ResidenceFactory(current_price_eur=500_000)

        response = client.get(self.endpoint, {"max_price": 300_000})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 200_000

    def test_filter_by_price_range(self, client):
        ResidenceFactory(current_price_eur=100_000)
        ResidenceFactory(current_price_eur=300_000)
        ResidenceFactory(current_price_eur=600_000)

        response = client.get(self.endpoint, {"min_price": 200_000, "max_price": 400_000})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["current_price_eur"] == 300_000

    def test_filter_by_status(self, client):
        ResidenceFactory(current_status="new")
        ResidenceFactory(current_status="sold")

        response = client.get(self.endpoint, {"status": "new"})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["current_status"] == "new"

    def test_multiple_filters_combined(self, client):
        ResidenceFactory(city="Amsterdam", current_price_eur=300_000)
        ResidenceFactory(city="Amsterdam", current_price_eur=800_000)
        ResidenceFactory(city="Rotterdam", current_price_eur=300_000)

        response = client.get(self.endpoint, {"city": "amsterdam", "max_price": 500_000})

        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["city"] == "Amsterdam"
        assert data[0]["current_price_eur"] == 300_000

    def test_default_pagination(self, client):
        for _ in range(25):
            ResidenceFactory()

        response = client.get(self.endpoint)

        assert len(response.json()["items"]) == 20

    def test_custom_limit(self, client):
        for _ in range(10):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 5})

        assert len(response.json()["items"]) == 5

    def test_custom_offset(self, client):
        for _ in range(10):
            ResidenceFactory()

        response = client.get(self.endpoint, {"limit": 5, "offset": 5})

        assert len(response.json()["items"]) == 5

    def test_offset_beyond_results(self, client):
        ResidenceFactory()

        response = client.get(self.endpoint, {"offset": 100})

        assert response.json()["items"] == []

    def test_limit_clamped_to_max(self, client):
        response = client.get(self.endpoint, {"limit": 200})

        assert response.status_code == 422

    def test_limit_rejects_negative(self, client):
        response = client.get(self.endpoint, {"limit": -1})

        assert response.status_code == 422

    def test_offset_must_be_non_negative(self, client):
        response = client.get(self.endpoint, {"offset": -1})

        assert response.status_code == 422

    def test_ordered_by_newest_first(self, client):
        r1 = ResidenceFactory()
        r2 = ResidenceFactory()

        now = datetime.now(UTC)
        Residence.objects.filter(pk=r1.pk).update(created_at=now - timedelta(seconds=10))  # ty: ignore[unresolved-attribute]
        Residence.objects.filter(pk=r2.pk).update(created_at=now)  # ty: ignore[unresolved-attribute]

        response = client.get(self.endpoint)

        ids = [r["id"] for r in response.json()["items"]]
        assert ids == [r2.id, r1.id]  # ty: ignore[unresolved-attribute]

    def test_no_n_plus_one_queries(self, client, django_assert_num_queries):
        for _ in range(3):
            residence = ResidenceFactory()
            ListingFactory.create_batch(2, residence=residence)

        with django_assert_num_queries(2):  # count + main (cover image is an inlined subquery)
            client.get(self.endpoint)

    def test_item_shape_is_slim(self, client):
        residence = ResidenceFactory(bedroom_count=3, bathroom_count=2, surface_area_m2=120, energy_label="A")
        ListingFactory(residence=residence, image_url="https://example.com/cover.jpg")

        response = client.get(self.endpoint)

        item = response.json()["items"][0]
        assert set(item) == {
            "id",
            "city",
            "street",
            "house_number",
            "house_letter",
            "house_number_suffix",
            "postcode",
            "slug",
            "latitude",
            "longitude",
            "current_price_eur",
            "current_status",
            "surface_area_m2",
            "bedroom_count",
            "bathroom_count",
            "energy_label",
            "image_url",
        }
        assert item["bedroom_count"] == 3
        assert item["image_url"] == "https://example.com/cover.jpg"

    def test_excludes_ungeocoded_residences(self, client):
        ResidenceFactory(latitude=None, longitude=None)
        geocoded = ResidenceFactory()

        response = client.get(self.endpoint)

        body = response.json()
        assert body["total"] == 1
        assert [i["id"] for i in body["items"]] == [geocoded.id]  # ty: ignore[unresolved-attribute]

    def test_cover_image_prefers_freshest_listing(self, client):
        residence = ResidenceFactory()
        ListingFactory(
            residence=residence,
            image_url="https://example.com/old.jpg",
            list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        ListingFactory(
            residence=residence,
            image_url="https://example.com/new.jpg",
            list_scraped_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] == "https://example.com/new.jpg"

    def test_cover_image_null_timestamp_loses(self, client):
        residence = ResidenceFactory()
        ListingFactory(residence=residence, image_url="https://example.com/null-ts.jpg", list_scraped_at=None)
        ListingFactory(
            residence=residence,
            image_url="https://example.com/dated.jpg",
            list_scraped_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] == "https://example.com/dated.jpg"

    def test_cover_image_skips_listings_without_image(self, client):
        residence = ResidenceFactory()
        ListingFactory(
            residence=residence,
            image_url=None,
            list_scraped_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        ListingFactory(
            residence=residence,
            image_url="https://example.com/only.jpg",
            list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] == "https://example.com/only.jpg"

    def test_cover_image_ignores_bag_status(self, client):
        residence = ResidenceFactory()
        ListingFactory(
            residence=residence,
            image_url="https://example.com/pending.jpg",
            bag_status=BagStatus.PENDING,
            list_scraped_at=datetime(2026, 6, 1, tzinfo=UTC),
        )

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] == "https://example.com/pending.jpg"

    def test_cover_image_skips_empty_string_image(self, client):
        residence = ResidenceFactory()
        ListingFactory(
            residence=residence,
            image_url="",
            list_scraped_at=datetime(2026, 6, 1, tzinfo=UTC),
        )
        ListingFactory(
            residence=residence,
            image_url="https://example.com/real.jpg",
            list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] == "https://example.com/real.jpg"

    def test_cover_image_null_when_no_listing_has_image(self, client):
        residence = ResidenceFactory()
        ListingFactory(residence=residence, image_url=None)

        response = client.get(self.endpoint)

        assert response.json()["items"][0]["image_url"] is None
