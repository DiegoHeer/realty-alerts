from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import AdminSite

from scraping.admin import ResidenceAdmin
from scraping.models import Residence
from tests.factories import ListingFactory, ResidenceFactory


@pytest.fixture
def admin():
    return ResidenceAdmin(Residence, AdminSite())


@pytest.mark.django_db
class TestListingCount:
    def test_listing_count_display_method(self, admin, rf):
        residence = cast(Residence, ResidenceFactory())
        ListingFactory(residence=residence)

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        obj = qs.get(pk=residence.pk)
        assert admin.listing_count(obj) == 1

    def test_listing_count_isolated_per_residence(self, admin, rf):
        r1 = cast(Residence, ResidenceFactory())
        r2 = cast(Residence, ResidenceFactory())
        ListingFactory(residence=r1)
        ListingFactory(residence=r1)
        ListingFactory(residence=r2)

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        assert qs.get(pk=r1.pk).listing_count == 2
        assert qs.get(pk=r2.pk).listing_count == 1

    def test_listing_count_zero(self, admin, rf):
        residence = cast(Residence, ResidenceFactory())

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        obj = qs.get(pk=residence.pk)
        assert admin.listing_count(obj) == 0

    def test_listing_count_in_list_display(self, admin):
        assert "listing_count" in admin.list_display


@pytest.mark.django_db
class TestDetailFields:
    def test_fields_from_freshest_listing(self, admin):
        residence = cast(Residence, ResidenceFactory())
        ListingFactory(
            residence=residence,
            detail_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
            energy_label="A",
            room_count=4,
            bedroom_count=2,
            bathroom_count=1,
            surface_area_m2=85,
            construction_period="2000-2010",
        )
        ListingFactory(
            residence=residence,
            detail_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
            energy_label="B",
            room_count=5,
            bedroom_count=3,
            bathroom_count=2,
            surface_area_m2=110,
            construction_period="1990-2000",
        )

        assert admin.display_room_count(residence) == 5
        assert admin.display_bedroom_count(residence) == 3
        assert admin.display_bathroom_count(residence) == 2
        assert admin.display_surface_area_m2(residence) == 110
        assert admin.display_construction_period(residence) == "1990-2000"
        assert admin.display_detail_scraped_at(residence) == datetime(2026, 5, 1, tzinfo=UTC)

    def test_fields_empty_when_no_detail_scraped(self, admin):
        residence = cast(Residence, ResidenceFactory())
        ListingFactory(residence=residence, detail_scraped_at=None)

        assert admin.display_room_count(residence) == "—"
        assert admin.display_bedroom_count(residence) == "—"
        assert admin.display_bathroom_count(residence) == "—"
        assert admin.display_surface_area_m2(residence) == "—"
        assert admin.display_construction_period(residence) == "—"
        assert admin.display_detail_scraped_at(residence) == "—"

    def test_fields_empty_when_no_listings(self, admin):
        residence = cast(Residence, ResidenceFactory())

        assert admin.display_room_count(residence) == "—"

    def test_individual_null_fields_show_dash(self, admin):
        residence = cast(Residence, ResidenceFactory())
        ListingFactory(
            residence=residence,
            detail_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
            energy_label=None,
            room_count=3,
        )

        assert admin.display_room_count(residence) == 3

    def test_freshest_listing_cached_across_fields(self, admin, django_assert_num_queries):
        residence = cast(Residence, ResidenceFactory())
        ListingFactory(
            residence=residence,
            detail_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
            energy_label="A",
            room_count=4,
        )

        with django_assert_num_queries(1):
            admin.display_room_count(residence)
            admin.display_detail_scraped_at(residence)


class TestFieldsets:
    def test_ep_online_fieldset_present(self, admin):
        fieldset_names = [name for name, _ in admin.fieldsets]
        assert "Building Details (EP-Online)" in fieldset_names

    def test_ep_online_fieldset_contains_fields(self, admin):
        ep_fieldset = None
        for name, options in admin.fieldsets:
            if name == "Building Details (EP-Online)":
                ep_fieldset = options
                break
        expected_fields = {"building_type", "energy_label", "energy_label_valid_until"}
        assert ep_fieldset is not None, "EP-Online fieldset not found"
        assert expected_fields == set(ep_fieldset["fields"])

    def test_ep_online_fields_in_readonly_fields(self, admin):
        assert "building_type" in admin.readonly_fields
        assert "energy_label" in admin.readonly_fields
        assert "energy_label_valid_until" in admin.readonly_fields

    def test_building_type_in_list_display(self, admin):
        assert "building_type" in admin.list_display

    def test_building_type_in_list_filter(self, admin):
        assert "building_type" in admin.list_filter

    def test_detail_fieldset_present(self, admin):
        fieldset_names = [name for name, _ in admin.fieldsets]
        assert "Listing Details (latest scrape)" in fieldset_names

    def test_detail_fieldset_contains_display_methods(self, admin):
        detail_fieldset = None
        for name, options in admin.fieldsets:
            if name == "Listing Details (latest scrape)":
                detail_fieldset = options
                break
        expected_fields = {
            "display_room_count",
            "display_bedroom_count",
            "display_bathroom_count",
            "display_surface_area_m2",
            "display_construction_period",
            "display_detail_scraped_at",
        }
        assert detail_fieldset is not None, "Listing Details fieldset not found"
        assert expected_fields == set(detail_fieldset["fields"])

    def test_detail_display_methods_in_readonly_fields(self, admin):
        assert "display_room_count" in admin.readonly_fields
        assert "display_bedroom_count" in admin.readonly_fields
        assert "display_bathroom_count" in admin.readonly_fields
        assert "display_surface_area_m2" in admin.readonly_fields
        assert "display_construction_period" in admin.readonly_fields
        assert "display_detail_scraped_at" in admin.readonly_fields


@pytest.mark.django_db
class TestEnrichActions:
    def test_enrich_location_dispatches_tasks(self, admin_client):
        r1 = cast(Residence, ResidenceFactory())
        r2 = cast(Residence, ResidenceFactory())
        with patch("scraping.admin.enrich_location.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/residence/",
                {"action": "enrich_location_action", "_selected_action": [r1.pk, r2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(r1.pk)
        mock_delay.assert_any_call(r2.pk)

    def test_enrich_building_details_dispatches_tasks(self, admin_client):
        r1 = cast(Residence, ResidenceFactory())
        r2 = cast(Residence, ResidenceFactory())
        with patch("scraping.admin.enrich_building_details.delay") as mock_delay:
            admin_client.post(
                "/admin/scraping/residence/",
                {"action": "enrich_building_details_action", "_selected_action": [r1.pk, r2.pk]},
            )
        assert mock_delay.call_count == 2
        mock_delay.assert_any_call(r1.pk)
        mock_delay.assert_any_call(r2.pk)
