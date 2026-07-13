from datetime import datetime, timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
from django.db.models import QuerySet
from loguru import logger

from scraping.models import ListingStatus, Residence

RESIDENCE_TERMINAL_TTL_DAYS = 365
TERMINAL_STATUSES = (ListingStatus.SOLD, ListingStatus.SALE_PENDING)

UNVERIFIED_ACCOUNT_TTL_DAYS = 7


def delete_expired_terminal_residences(*, now: datetime) -> int:
    """Hard-delete residences that have been in a terminal status (sold or
    sale_pending) for longer than RESIDENCE_TERMINAL_TTL_DAYS. Residences whose
    `status_changed_at` is NULL are excluded (SQL `<` is unknown for NULL)."""
    cutoff = now - timedelta(days=RESIDENCE_TERMINAL_TTL_DAYS)

    deleted, _ = Residence.objects.filter(current_status__in=TERMINAL_STATUSES, status_changed_at__lt=cutoff).delete()
    if deleted:
        logger.info("residence_ttl_deleted deleted={} cutoff={}", deleted, cutoff.isoformat())

    return deleted


def stale_unverified_users(*, now: datetime) -> QuerySet[User]:
    """Accounts that never completed email verification within
    UNVERIFIED_ACCOUNT_TTL_DAYS of signing up: at least one EmailAddress, none of
    them verified, past the TTL, and not staff/superuser. Users with no
    EmailAddress at all (not signup leftovers) are excluded."""
    cutoff = now - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS)
    verified_user_ids = EmailAddress.objects.filter(verified=True).values_list("user_id", flat=True)
    unverified_user_ids = EmailAddress.objects.filter(verified=False).values_list("user_id", flat=True)
    return User.objects.filter(
        pk__in=unverified_user_ids,
        date_joined__lt=cutoff,
        is_staff=False,
        is_superuser=False,
    ).exclude(pk__in=verified_user_ids)


def delete_unverified_accounts(*, now: datetime) -> int:
    """Hard-delete stale unverified accounts; cascades to their EmailAddress
    rows. Returns the number of accounts deleted."""
    _, deleted_by_model = stale_unverified_users(now=now).delete()
    deleted = deleted_by_model.get("auth.User", 0)
    if deleted:
        cutoff = now - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS)
        logger.info("unverified_account_ttl_deleted deleted={} cutoff={}", deleted, cutoff.isoformat())
    return deleted
