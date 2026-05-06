from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from scraping.cleanup import RESIDENCE_TERMINAL_TTL_DAYS, delete_expired_terminal_residences
from scraping.models import ListingStatus, Residence
from tests.factories import ResidenceFactory


def _make(**kwargs) -> Residence:
    return cast(Residence, ResidenceFactory(**kwargs))


NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
PAST_TTL = NOW - timedelta(days=RESIDENCE_TERMINAL_TTL_DAYS + 1)
WITHIN_TTL = NOW - timedelta(days=RESIDENCE_TERMINAL_TTL_DAYS - 1)


@pytest.mark.django_db
def test_deletes_sold_residence_past_ttl():
    ResidenceFactory(status=ListingStatus.SOLD, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 1
    assert not Residence.objects.exists()


@pytest.mark.django_db
def test_deletes_sale_pending_residence_past_ttl():
    ResidenceFactory(status=ListingStatus.SALE_PENDING, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 1
    assert not Residence.objects.exists()


@pytest.mark.django_db
def test_keeps_new_residence_even_if_status_changed_at_is_old():
    residence = _make(status=ListingStatus.NEW, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 0
    assert Residence.objects.filter(pk=residence.pk).exists()


@pytest.mark.django_db
def test_keeps_terminal_residence_within_ttl_window():
    residence = _make(status=ListingStatus.SOLD, status_changed_at=WITHIN_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 0
    assert Residence.objects.filter(pk=residence.pk).exists()


@pytest.mark.django_db
def test_keeps_terminal_residence_with_null_status_changed_at():
    residence = _make(status=ListingStatus.SOLD, status_changed_at=None)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 0
    assert Residence.objects.filter(pk=residence.pk).exists()


@pytest.mark.django_db
def test_mixed_batch_deletes_only_eligible_rows():
    expired_sold = _make(status=ListingStatus.SOLD, status_changed_at=PAST_TTL)
    expired_pending = _make(status=ListingStatus.SALE_PENDING, status_changed_at=PAST_TTL)
    fresh_sold = _make(status=ListingStatus.SOLD, status_changed_at=WITHIN_TTL)
    new_old = _make(status=ListingStatus.NEW, status_changed_at=PAST_TTL)
    null_anchor = _make(status=ListingStatus.SOLD, status_changed_at=None)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 2
    surviving_pks = set(Residence.objects.values_list("pk", flat=True))
    assert surviving_pks == {fresh_sold.pk, new_old.pk, null_anchor.pk}
    assert not Residence.objects.filter(pk__in=[expired_sold.pk, expired_pending.pk]).exists()


@pytest.mark.django_db
def test_returns_zero_when_nothing_to_delete():
    ResidenceFactory(status=ListingStatus.NEW, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 0


@pytest.mark.django_db
def test_uses_current_status_when_legacy_disagrees():
    """Cross-portal: legacy `status` regressed to NEW because the freshest
    portal saw NEW, but `current_status` rolled up to SOLD via reconciliation
    (another portal marked it sold). Cleanup must follow `current_status`."""
    regressed = _make(status=ListingStatus.NEW, current_status=ListingStatus.SOLD, status_changed_at=PAST_TTL)
    matching_legacy = _make(status=ListingStatus.SOLD, current_status=ListingStatus.NEW, status_changed_at=PAST_TTL)

    deleted = delete_expired_terminal_residences(now=NOW)

    assert deleted == 1
    surviving_pks = set(Residence.objects.values_list("pk", flat=True))
    assert surviving_pks == {matching_legacy.pk}
    assert not Residence.objects.filter(pk=regressed.pk).exists()
