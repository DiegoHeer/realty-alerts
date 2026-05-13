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
        residence = ResidenceFactory()
        ListingFactory(residence=residence)

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        obj = qs.get(pk=residence.pk)
        assert admin.listing_count(obj) == 1

    def test_listing_count_isolated_per_residence(self, admin, rf):
        r1 = ResidenceFactory()
        r2 = ResidenceFactory()
        ListingFactory(residence=r1)
        ListingFactory(residence=r1)
        ListingFactory(residence=r2)

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        assert qs.get(pk=r1.pk).listing_count == 2
        assert qs.get(pk=r2.pk).listing_count == 1

    def test_listing_count_zero(self, admin, rf):
        residence = ResidenceFactory()

        request = rf.get("/admin/scraping/residence/")
        qs = admin.get_queryset(request)
        obj = qs.get(pk=residence.pk)
        assert admin.listing_count(obj) == 0

    def test_listing_count_in_list_display(self, admin):
        assert "listing_count" in admin.list_display
