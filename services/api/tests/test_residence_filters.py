import math
import pytest
from datetime import UTC, datetime

from scraping.models import Residence
from scraping.api import _parse_near, _radius_bbox
from ninja.errors import HttpError
from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestResidenceFilters:
    endpoint = "/v1/residences"

    def test_deal_type_sale_is_default(self, client):
        ResidenceFactory()
        response = client.get(self.endpoint)
        assert len(response.json()["items"]) == 1

    def test_deal_type_rent_returns_empty(self, client):
        ResidenceFactory()  # backfilled to sale
        response = client.get(self.endpoint, {"deal_type": "rent"})
        assert response.json()["items"] == []

    def test_deal_type_invalid_422(self, client):
        response = client.get(self.endpoint, {"deal_type": "lease"})
        assert response.status_code == 422

    def test_building_type_single(self, client):
        apartment = ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="detached")
        response = client.get(self.endpoint, {"building_type": "apartment"})
        data = response.json()["items"]
        assert len(data) == 1
        assert data[0]["id"] == apartment.id  # ty: ignore[unresolved-attribute]

    def test_building_type_or_repeated(self, client):
        ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="terraced")
        ResidenceFactory(building_type="detached")
        response = client.get(f"{self.endpoint}?building_type=apartment&building_type=terraced")
        assert len(response.json()["items"]) == 2

    def test_building_type_csv_fallback(self, client):
        ResidenceFactory(building_type="apartment")
        ResidenceFactory(building_type="terraced")
        ResidenceFactory(building_type="detached")
        response = client.get(self.endpoint, {"building_type": "apartment,terraced"})
        assert len(response.json()["items"]) == 2

    def test_building_type_invalid_422(self, client):
        response = client.get(self.endpoint, {"building_type": "castle"})
        assert response.status_code == 422

    def test_building_type_null_excluded(self, client):
        ResidenceFactory(building_type=None)
        response = client.get(self.endpoint, {"building_type": "apartment"})
        assert response.json()["items"] == []

    def test_energy_label_or_repeated(self, client):
        ResidenceFactory(energy_label="A")
        ResidenceFactory(energy_label="B")
        ResidenceFactory(energy_label="G")
        response = client.get(f"{self.endpoint}?energy_label=A&energy_label=B")
        assert len(response.json()["items"]) == 2

    def test_energy_label_full_enum_value(self, client):
        ResidenceFactory(energy_label="A++++")
        ResidenceFactory(energy_label="C")
        response = client.get(self.endpoint, {"energy_label": "A++++"})  # urlencode escapes '+'
        assert len(response.json()["items"]) == 1

    def test_energy_label_invalid_422(self, client):
        response = client.get(self.endpoint, {"energy_label": "Z"})
        assert response.status_code == 422

    def test_bbox_includes_point_inside(self, client):
        ResidenceFactory(latitude=52.08, longitude=4.29)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert len(response.json()["items"]) == 1

    def test_bbox_excludes_point_outside(self, client):
        ResidenceFactory(latitude=53.0, longitude=5.0)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert response.json()["items"] == []

    def test_bbox_excludes_null_coordinates(self, client):
        ResidenceFactory(latitude=None, longitude=None)
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32,52.10"})
        assert response.json()["items"] == []

    def test_bbox_inverted_returns_empty(self, client):
        ResidenceFactory(latitude=52.08, longitude=4.29)
        response = client.get(self.endpoint, {"bbox": "4.32,52.10,4.26,52.06"})
        assert response.json()["items"] == []

    def test_bbox_malformed_422(self, client):
        response = client.get(self.endpoint, {"bbox": "4.26,52.06,4.32"})
        assert response.status_code == 422

    def test_bbox_out_of_range_422(self, client):
        response = client.get(self.endpoint, {"bbox": "4.26,99.0,4.32,100.0"})
        assert response.status_code == 422

    def test_bbox_longitude_out_of_range_422(self, client):
        response = client.get(self.endpoint, {"bbox": "200.0,52.0,210.0,53.0"})
        assert response.status_code == 422

    def test_min_price_above_max_price_returns_empty(self, client):
        ResidenceFactory(current_price_eur=300_000)
        response = client.get(self.endpoint, {"min_price": 500_000, "max_price": 400_000})
        assert response.json()["items"] == []

    def test_default_order_id_tiebreaker(self, client):
        residences = [ResidenceFactory() for _ in range(5)]
        now = datetime.now(UTC)
        pks = [r.pk for r in residences]  # ty: ignore[unresolved-attribute]
        Residence.objects.filter(pk__in=pks).update(created_at=now)
        response = client.get(self.endpoint)
        ids = [r["id"] for r in response.json()["items"]]
        assert ids == sorted(ids, reverse=True)
        assert set(ids) == {r.id for r in residences}  # ty: ignore[unresolved-attribute]


class TestParseNear:
    def test_parses_lon_lat(self):
        assert _parse_near("4.8841,52.3676") == (4.8841, 52.3676)

    def test_wrong_count_raises_422(self):
        with pytest.raises(HttpError) as exc:
            _parse_near("4.8841")
        assert exc.value.status_code == 422

    def test_non_numeric_raises_422(self):
        with pytest.raises(HttpError) as exc:
            _parse_near("abc,52.0")
        assert exc.value.status_code == 422

    def test_longitude_out_of_range_raises_422(self):
        with pytest.raises(HttpError) as exc:
            _parse_near("200.0,52.0")
        assert exc.value.status_code == 422

    def test_latitude_out_of_range_raises_422(self):
        with pytest.raises(HttpError) as exc:
            _parse_near("4.0,200.0")
        assert exc.value.status_code == 422


class TestRadiusBbox:
    def test_box_encloses_center(self):
        min_lon, min_lat, max_lon, max_lat = _radius_bbox(4.8841, 52.3676, 1000)
        assert min_lon < 4.8841 < max_lon
        assert min_lat < 52.3676 < max_lat

    def test_latitude_delta_matches_meters(self):
        # 1000 m north/south ≈ 1000 / 111_320 degrees of latitude
        _, min_lat, _, max_lat = _radius_bbox(4.8841, 52.3676, 1000)
        expected_delta = 1000 / 111_320
        assert math.isclose((max_lat - min_lat) / 2, expected_delta, rel_tol=1e-6)

    def test_pole_latitude_does_not_blow_up(self):
        # cos(lat) → 0 at the poles; the clamp keeps lon_delta finite instead of
        # dividing by ~0 and producing a full-width box.
        min_lon, _, max_lon, _ = _radius_bbox(0.0, 90.0, 1000)
        assert max_lon - min_lon <= 360


@pytest.mark.django_db
class TestRadiusFilter:
    endpoint = "/v1/residences"

    def test_includes_point_inside_radius(self, client):
        r = ResidenceFactory(latitude=52.3676, longitude=4.8841)
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 1000})
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == r.id  # ty: ignore[unresolved-attribute]

    def test_excludes_point_outside_radius(self, client):
        # ~2 km north of the center, radius only 1 km
        ResidenceFactory(latitude=52.3856, longitude=4.8841)
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 1000})
        assert response.json()["items"] == []

    def test_point_just_outside_is_excluded_but_larger_radius_includes(self, client):
        ResidenceFactory(latitude=52.3856, longitude=4.8841)
        small = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 1000})
        big = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 5000})
        assert small.json()["items"] == []
        assert len(big.json()["items"]) == 1

    def test_radius_combines_with_price_filter(self, client):
        ResidenceFactory(latitude=52.3676, longitude=4.8841, current_price_eur=400_000)
        ResidenceFactory(latitude=52.3676, longitude=4.8841, current_price_eur=900_000)
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 1000, "max_price": 500_000})
        assert len(response.json()["items"]) == 1

    def test_radius_combines_with_bbox_intersection(self, client):
        # inside radius but outside the bbox → excluded
        ResidenceFactory(latitude=52.3676, longitude=4.8841)
        response = client.get(
            self.endpoint,
            {"near": "4.8841,52.3676", "radius_m": 5000, "bbox": "5.0,52.0,5.1,52.1"},
        )
        assert response.json()["items"] == []

    def test_radius_without_near_returns_422(self, client):
        response = client.get(self.endpoint, {"radius_m": 1000})
        assert response.status_code == 422

    def test_radius_zero_returns_422(self, client):
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 0})
        assert response.status_code == 422

    def test_radius_over_cap_returns_422(self, client):
        response = client.get(self.endpoint, {"near": "4.8841,52.3676", "radius_m": 50001})
        assert response.status_code == 422

    def test_near_alone_is_allowed(self, client):
        ResidenceFactory(latitude=52.3676, longitude=4.8841)
        response = client.get(self.endpoint, {"near": "4.8841,52.3676"})
        assert response.status_code == 200
        assert len(response.json()["items"]) == 1
