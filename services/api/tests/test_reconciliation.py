from datetime import UTC, datetime
from typing import cast

import pytest

from scraping.models import BagStatus, ListingStatus, Residence
from scraping.reconciliation import reconcile_residence
from tests.factories import ListingFactory, ResidenceFactory

pytestmark = pytest.mark.django_db


def test_reconcile_with_no_resolved_listings_is_noop():
    residence = cast(Residence, ResidenceFactory(current_price_eur=500_000))
    initial_anchor = residence.status_changed_at

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_price_eur == 500_000
    assert residence.status_changed_at == initial_anchor


def test_reconcile_picks_min_price_across_resolved_listings():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=500_000)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=480_000)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=520_000)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_price_eur == 480_000


def test_reconcile_picks_most_advanced_status():
    residence = cast(Residence, ResidenceFactory(current_status=ListingStatus.NEW))
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, status=ListingStatus.NEW)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, status=ListingStatus.SOLD)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, status=ListingStatus.SALE_PENDING)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_status == ListingStatus.SOLD


def test_reconcile_picks_max_list_scraped_at():
    residence = cast(Residence, ResidenceFactory())
    earliest = datetime(2026, 1, 1, tzinfo=UTC)
    latest = datetime(2026, 5, 1, tzinfo=UTC)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, list_scraped_at=earliest)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, list_scraped_at=latest)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.last_scraped_at == latest


def test_reconcile_ignores_unresolved_listings():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=500_000)
    ListingFactory(residence=residence, bag_status=BagStatus.PENDING, price_eur=300_000)
    ListingFactory(residence=residence, bag_status=BagStatus.BAG_NO_MATCH, price_eur=200_000)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_price_eur == 500_000


def test_reconcile_bumps_status_changed_at_on_transition():
    residence = cast(Residence, ResidenceFactory(current_status=ListingStatus.NEW))
    initial_anchor = residence.status_changed_at
    assert initial_anchor is not None
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, status=ListingStatus.SOLD)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_status == ListingStatus.SOLD
    assert residence.status_changed_at is not None
    assert residence.status_changed_at > initial_anchor


def test_reconcile_does_not_bump_status_changed_at_when_unchanged():
    residence = cast(Residence, ResidenceFactory(current_status=ListingStatus.NEW))
    initial_anchor = residence.status_changed_at
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, status=ListingStatus.NEW)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.status_changed_at == initial_anchor


def test_reconcile_skips_listings_with_null_price():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=None)
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=410_000)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_price_eur == 410_000


def test_reconcile_clears_current_price_when_no_listing_has_price():
    residence = cast(Residence, ResidenceFactory(current_price_eur=300_000))
    ListingFactory(residence=residence, bag_status=BagStatus.RESOLVED, price_eur=None)

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.current_price_eur is None


def test_reconcile_picks_construction_type_from_freshest_listing():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        construction_type="bestaande_bouw",
    )
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        construction_type="nieuwbouw",
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.construction_type == "nieuwbouw"


def test_reconcile_construction_type_ignores_null_values():
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        construction_type=None,
    )
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 1, 1, tzinfo=UTC),
        construction_type="bestaande_bouw",
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.construction_type == "bestaande_bouw"


def test_reconcile_fills_building_type_when_residence_has_none():
    residence = cast(Residence, ResidenceFactory(building_type=None))
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        building_type="terraced",
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.building_type == "terraced"


def test_reconcile_does_not_overwrite_existing_building_type():
    residence = cast(Residence, ResidenceFactory(building_type="apartment"))
    ListingFactory(
        residence=residence,
        bag_status=BagStatus.RESOLVED,
        list_scraped_at=datetime(2026, 5, 1, tzinfo=UTC),
        building_type="terraced",
    )

    reconcile_residence(residence)

    residence.refresh_from_db()
    assert residence.building_type == "apartment"
