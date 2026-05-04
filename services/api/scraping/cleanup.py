from datetime import datetime, timedelta

from loguru import logger

from scraping.models import ListingStatus, Residence

RESIDENCE_TERMINAL_TTL_DAYS = 30
TERMINAL_STATUSES = (ListingStatus.SOLD, ListingStatus.SALE_PENDING)


def delete_expired_terminal_residences(*, now: datetime) -> int:
    """Hard-delete residences that have been in a terminal status (sold or
    sale_pending) for longer than RESIDENCE_TERMINAL_TTL_DAYS. Residences whose
    `status_changed_at` is NULL are excluded (SQL `<` is unknown for NULL)."""
    cutoff = now - timedelta(days=RESIDENCE_TERMINAL_TTL_DAYS)

    deleted, _ = Residence.objects.filter(status__in=TERMINAL_STATUSES, status_changed_at__lt=cutoff).delete()
    if deleted:
        logger.info("residence_ttl_deleted", deleted=deleted, cutoff=cutoff.isoformat())

    return deleted
