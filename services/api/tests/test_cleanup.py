from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from scraping.cleanup import LISTING_TERMINAL_TTL_DAYS, delete_expired_terminal_listings
from scraping.models import Listing, ListingStatus
from tests.factories import ListingFactory


def _make(**kwargs) -> Listing:
    return cast(Listing, ListingFactory(**kwargs))

NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
PAST_TTL = NOW - timedelta(days=LISTING_TERMINAL_TTL_DAYS + 1)
WITHIN_TTL = NOW - timedelta(days=LISTING_TERMINAL_TTL_DAYS - 1)


@pytest.mark.django_db
def test_deletes_sold_listing_past_ttl():
    ListingFactory(status=ListingStatus.SOLD, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 1
    assert not Listing.objects.exists()


@pytest.mark.django_db
def test_deletes_sale_pending_listing_past_ttl():
    ListingFactory(status=ListingStatus.SALE_PENDING, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 1
    assert not Listing.objects.exists()


@pytest.mark.django_db
def test_keeps_new_listing_even_if_status_changed_at_is_old():
    listing = _make(status=ListingStatus.NEW, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 0
    assert Listing.objects.filter(pk=listing.pk).exists()


@pytest.mark.django_db
def test_keeps_terminal_listing_within_ttl_window():
    listing = _make(status=ListingStatus.SOLD, status_changed_at=WITHIN_TTL)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 0
    assert Listing.objects.filter(pk=listing.pk).exists()


@pytest.mark.django_db
def test_keeps_terminal_listing_with_null_status_changed_at():
    listing = _make(status=ListingStatus.SOLD, status_changed_at=None)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 0
    assert Listing.objects.filter(pk=listing.pk).exists()


@pytest.mark.django_db
def test_mixed_batch_deletes_only_eligible_rows():
    expired_sold = _make(status=ListingStatus.SOLD, status_changed_at=PAST_TTL)
    expired_pending = _make(status=ListingStatus.SALE_PENDING, status_changed_at=PAST_TTL)
    fresh_sold = _make(status=ListingStatus.SOLD, status_changed_at=WITHIN_TTL)
    new_old = _make(status=ListingStatus.NEW, status_changed_at=PAST_TTL)
    null_anchor = _make(status=ListingStatus.SOLD, status_changed_at=None)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 2
    surviving_pks = set(Listing.objects.values_list("pk", flat=True))
    assert surviving_pks == {fresh_sold.pk, new_old.pk, null_anchor.pk}
    assert not Listing.objects.filter(pk__in=[expired_sold.pk, expired_pending.pk]).exists()


@pytest.mark.django_db
def test_returns_zero_when_nothing_to_delete():
    ListingFactory(status=ListingStatus.NEW, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_listings(now=NOW)

    assert deleted == 0
