from datetime import UTC, datetime, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from scraping.cleanup import UNVERIFIED_ACCOUNT_TTL_DAYS, delete_unverified_accounts

NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
PAST_TTL = NOW - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
WITHIN_TTL = NOW - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS - 1)


def _account(
    email: str,
    *,
    joined: datetime,
    verified: bool,
    is_staff: bool = False,
    is_superuser: bool = False,
    with_email: bool = True,
) -> User:
    user = User.objects.create_user(
        username=email,
        email=email,
        password="testpass123!",
        date_joined=joined,
        is_staff=is_staff,
        is_superuser=is_superuser,
    )
    if with_email:
        EmailAddress.objects.create(user=user, email=email, verified=verified, primary=True)
    return user


@pytest.mark.django_db
def test_deletes_unverified_account_past_ttl():
    _account("stale@example.com", joined=PAST_TTL, verified=False)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 1
    assert not User.objects.filter(email="stale@example.com").exists()


@pytest.mark.django_db
def test_cascade_removes_email_address():
    user = _account("stale@example.com", joined=PAST_TTL, verified=False)

    delete_unverified_accounts(now=NOW)

    assert not EmailAddress.objects.filter(user_id=user.pk).exists()


@pytest.mark.django_db
def test_keeps_unverified_account_within_ttl():
    _account("fresh@example.com", joined=WITHIN_TTL, verified=False)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 0
    assert User.objects.filter(email="fresh@example.com").exists()


@pytest.mark.django_db
def test_keeps_verified_account_even_when_old():
    _account("verified@example.com", joined=PAST_TTL, verified=True)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 0
    assert User.objects.filter(email="verified@example.com").exists()


@pytest.mark.django_db
def test_keeps_account_with_any_verified_email():
    # A verified primary plus a later unverified secondary email still counts as
    # a completed registration — the user must be kept.
    user = _account("mixed@example.com", joined=PAST_TTL, verified=True)
    EmailAddress.objects.create(user=user, email="second@example.com", verified=False, primary=False)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 0
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_keeps_staff_and_superuser():
    _account("staff@example.com", joined=PAST_TTL, verified=False, is_staff=True)
    _account("root@example.com", joined=PAST_TTL, verified=False, is_superuser=True)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 0
    assert User.objects.filter(email__in=["staff@example.com", "root@example.com"]).count() == 2


@pytest.mark.django_db
def test_keeps_account_without_any_email_record():
    # No EmailAddress at all (e.g. a programmatically created user) is not a
    # stale signup and must be left alone.
    _account("orphan@example.com", joined=PAST_TTL, verified=False, with_email=False)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 0
    assert User.objects.filter(email="orphan@example.com").exists()


@pytest.mark.django_db
def test_mixed_batch_deletes_only_eligible():
    _account("stale@example.com", joined=PAST_TTL, verified=False)
    _account("fresh@example.com", joined=WITHIN_TTL, verified=False)
    _account("verified@example.com", joined=PAST_TTL, verified=True)
    _account("staff@example.com", joined=PAST_TTL, verified=False, is_staff=True)

    deleted = delete_unverified_accounts(now=NOW)

    assert deleted == 1
    surviving = set(User.objects.values_list("email", flat=True))
    assert surviving == {"fresh@example.com", "verified@example.com", "staff@example.com"}


@pytest.mark.django_db
def test_returns_zero_when_nothing_to_delete():
    _account("verified@example.com", joined=PAST_TTL, verified=True)

    assert delete_unverified_accounts(now=NOW) == 0


def _cleanup_url() -> str:
    return reverse("admin:auth_user_cleanup_unverified")


@pytest.mark.django_db
def test_confirm_page_lists_only_eligible_accounts(admin_client):
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    fresh = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS - 1)
    _account("stale@example.com", joined=old, verified=False)
    _account("fresh@example.com", joined=fresh, verified=False)
    _account("confirmed@example.com", joined=old, verified=True)

    response = admin_client.get(_cleanup_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "stale@example.com" in content
    assert "fresh@example.com" not in content
    assert "confirmed@example.com" not in content


@pytest.mark.django_db
def test_confirm_page_shows_empty_state(admin_client):
    response = admin_client.get(_cleanup_url())

    assert response.status_code == 200
    assert "No stale unverified accounts" in response.content.decode()


@pytest.mark.django_db
def test_get_does_not_delete(admin_client):
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    _account("stale@example.com", joined=old, verified=False)

    admin_client.get(_cleanup_url())

    assert User.objects.filter(email="stale@example.com").exists()


@pytest.mark.django_db
def test_post_deletes_and_redirects(admin_client):
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    _account("stale@example.com", joined=old, verified=False)

    response = admin_client.post(_cleanup_url())

    assert response.status_code == 302
    assert response.url == reverse("admin:auth_user_changelist")
    assert not User.objects.filter(email="stale@example.com").exists()


@pytest.mark.django_db
def test_staff_without_delete_permission_forbidden():
    staff = User.objects.create_user(username="viewer", password="testpass123!", is_staff=True)
    django_client = Client()
    django_client.force_login(staff)

    assert django_client.get(_cleanup_url()).status_code == 403
    assert django_client.post(_cleanup_url()).status_code == 403


@pytest.mark.django_db
def test_changelist_shows_cleanup_button(admin_client):
    response = admin_client.get(reverse("admin:auth_user_changelist"))

    assert _cleanup_url() in response.content.decode()


@pytest.mark.django_db
def test_anonymous_redirected_to_login():
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    _account("stale@example.com", joined=old, verified=False)

    response = Client().get(_cleanup_url())

    assert response.status_code == 302
    assert User.objects.filter(email="stale@example.com").exists()
