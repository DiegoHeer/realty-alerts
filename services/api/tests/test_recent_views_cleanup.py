from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from django.utils import timezone

from accounts.cleanup import RESIDENCE_VIEW_TTL_DAYS, delete_stale_residence_views
from accounts.models import ResidenceView
from scraping.models import Residence
from tests.factories import ResidenceFactory

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)
PAST_TTL = NOW - timedelta(days=RESIDENCE_VIEW_TTL_DAYS + 1)
WITHIN_TTL = NOW - timedelta(days=RESIDENCE_VIEW_TTL_DAYS - 1)


def _view(user, viewed_at) -> ResidenceView:
    return ResidenceView.objects.create(user=user, residence=cast(Residence, ResidenceFactory()), viewed_at=viewed_at)


@pytest.mark.django_db
def test_deletes_views_past_ttl(test_user):
    _view(test_user, PAST_TTL)
    deleted = delete_stale_residence_views(now=NOW)
    assert deleted == 1
    assert not ResidenceView.objects.exists()


@pytest.mark.django_db
def test_keeps_views_within_ttl(test_user):
    _view(test_user, WITHIN_TTL)
    deleted = delete_stale_residence_views(now=NOW)
    assert deleted == 0
    assert ResidenceView.objects.count() == 1


@pytest.mark.django_db
def test_task_runs_and_returns_count(test_user):
    from accounts.tasks import cleanup_stale_residence_views

    _view(test_user, timezone.now() - timedelta(days=RESIDENCE_VIEW_TTL_DAYS + 5))
    assert cleanup_stale_residence_views() == 1
