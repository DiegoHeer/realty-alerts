import importlib
from datetime import UTC, datetime
from typing import cast

import pytest
from django.apps import apps as global_apps

from scraping.models import BagStatus, Residence
from tests.factories import ListingFactory, ResidenceFactory

pytestmark = pytest.mark.django_db

_MIGRATION = "scraping.migrations.0028_backfill_residence_listing_attrs"


def _run_backfill():
    module = importlib.import_module(_MIGRATION)
    module.backfill(global_apps, None)


def test_backfill_populates_from_freshest_resolved_listing():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        bedroom_count=2,
        surface_area_m2=70,
        construction_period="1960",
    )
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        bedroom_count=4,
        bathroom_count=2,
        surface_area_m2=120,
        construction_period="1998",
    )
    # Simulate the pre-backfill state (columns empty).
    Residence.objects.filter(pk=residence.pk).update(
        bedroom_count=None, bathroom_count=None, surface_area_m2=None, build_year=None
    )

    _run_backfill()

    residence.refresh_from_db()
    assert residence.bedroom_count == 4
    assert residence.bathroom_count == 2
    assert residence.surface_area_m2 == 120
    assert residence.build_year == 1998


def test_backfill_ignores_residence_without_resolved_listings():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(residence=residence, bag_status=BagStatus.PENDING, bedroom_count=9)

    _run_backfill()

    residence.refresh_from_db()
    assert residence.bedroom_count is None
