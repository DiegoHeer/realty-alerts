from datetime import UTC, datetime, timedelta

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.core.management import call_command
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
def test_dry_run_reports_without_deleting():
    _account("stale@example.com", joined=PAST_TTL, verified=False)

    would_delete = delete_unverified_accounts(now=NOW, dry_run=True)

    assert would_delete == 1
    assert User.objects.filter(email="stale@example.com").exists()


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


@pytest.mark.django_db
def test_management_command_deletes_stale_accounts():
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    _account("stale@example.com", joined=old, verified=False)

    call_command("cleanup_unverified_accounts")

    assert not User.objects.filter(email="stale@example.com").exists()


@pytest.mark.django_db
def test_management_command_dry_run_keeps_accounts():
    old = timezone.now() - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS + 1)
    _account("stale@example.com", joined=old, verified=False)

    call_command("cleanup_unverified_accounts", "--dry-run")

    assert User.objects.filter(email="stale@example.com").exists()
