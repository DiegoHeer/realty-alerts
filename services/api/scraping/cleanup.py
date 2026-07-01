from datetime import datetime, timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import User
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
        logger.info("residence_ttl_deleted", deleted=deleted, cutoff=cutoff.isoformat())

    return deleted


def delete_unverified_accounts(*, now: datetime, dry_run: bool = False) -> int:
    """Hard-delete accounts that never completed email verification within
    UNVERIFIED_ACCOUNT_TTL_DAYS of signing up. An account is "unverified" when it
    has at least one EmailAddress and none of them are verified. Staff and
    superusers are always kept, as are users with no EmailAddress record at all
    (not signup leftovers). Returns the number of accounts deleted (or, with
    `dry_run`, that would be deleted)."""
    cutoff = now - timedelta(days=UNVERIFIED_ACCOUNT_TTL_DAYS)

    verified_user_ids = EmailAddress.objects.filter(verified=True).values_list("user_id", flat=True)
    unverified_user_ids = EmailAddress.objects.filter(verified=False).values_list("user_id", flat=True)
    stale_ids = list(
        User.objects.filter(
            pk__in=unverified_user_ids,
            date_joined__lt=cutoff,
            is_staff=False,
            is_superuser=False,
        )
        .exclude(pk__in=verified_user_ids)
        .values_list("pk", flat=True)
    )
    if not stale_ids:
        return 0

    if dry_run:
        logger.info("unverified_account_ttl_dry_run", would_delete=len(stale_ids), cutoff=cutoff.isoformat())
        return len(stale_ids)

    User.objects.filter(pk__in=stale_ids).delete()
    logger.info("unverified_account_ttl_deleted", deleted=len(stale_ids), cutoff=cutoff.isoformat())
    return len(stale_ids)
