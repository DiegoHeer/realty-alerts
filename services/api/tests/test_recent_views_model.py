from typing import cast

import pytest
from django.utils import timezone

from accounts.models import ResidenceView
from accounts.mru import upsert_and_evict
from scraping.models import Residence
from tests.factories import ResidenceFactory


@pytest.mark.django_db
def test_upsert_moves_to_front_without_duplicating(test_user):
    residence = cast(Residence, ResidenceFactory())
    now = timezone.now()
    upsert_and_evict(
        ResidenceView, user=test_user, residence=residence, timestamp_field="viewed_at", timestamp=now, cap=12
    )
    upsert_and_evict(
        ResidenceView, user=test_user, residence=residence, timestamp_field="viewed_at", timestamp=now, cap=12
    )
    assert ResidenceView.objects.filter(user=test_user).count() == 1


@pytest.mark.django_db
def test_evicts_beyond_cap_of_twelve(test_user):
    base = timezone.now()
    for n in range(15):
        upsert_and_evict(
            ResidenceView,
            user=test_user,
            residence=cast(Residence, ResidenceFactory()),
            timestamp_field="viewed_at",
            timestamp=base - timezone.timedelta(minutes=n),
            cap=12,
        )
    assert ResidenceView.objects.filter(user=test_user).count() == 12
