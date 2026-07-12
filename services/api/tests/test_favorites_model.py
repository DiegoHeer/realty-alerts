import pytest
from django.utils import timezone

from accounts.models import Favorite
from accounts.mru import upsert_and_evict
from tests.factories import ResidenceFactory


@pytest.mark.django_db
def test_upsert_creates_then_updates(test_user):
    residence = ResidenceFactory()
    now = timezone.now()
    upsert_and_evict(Favorite, user=test_user, residence=residence, timestamp_field="liked_at", timestamp=now, cap=200)
    upsert_and_evict(Favorite, user=test_user, residence=residence, timestamp_field="liked_at", timestamp=now, cap=200)
    assert Favorite.objects.filter(user=test_user).count() == 1  # upsert, not duplicate


@pytest.mark.django_db
def test_upsert_clamps_future_timestamp(test_user):
    residence = ResidenceFactory()
    future = timezone.now() + timezone.timedelta(days=3650)
    upsert_and_evict(Favorite, user=test_user, residence=residence, timestamp_field="liked_at", timestamp=future, cap=200)
    stored = Favorite.objects.get(user=test_user, residence=residence).liked_at
    assert stored <= timezone.now()


@pytest.mark.django_db
def test_evicts_oldest_beyond_cap(test_user):
    base = timezone.now()
    for n in range(5):
        upsert_and_evict(
            Favorite, user=test_user, residence=ResidenceFactory(),
            timestamp_field="liked_at", timestamp=base - timezone.timedelta(minutes=n), cap=3,
        )
    assert Favorite.objects.filter(user=test_user).count() == 3  # capped
