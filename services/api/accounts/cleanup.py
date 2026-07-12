from datetime import datetime, timedelta

from loguru import logger

from accounts.models import ResidenceView

RESIDENCE_VIEW_TTL_DAYS = 90


def delete_stale_residence_views(*, now: datetime) -> int:
    """Hard-delete residence views older than RESIDENCE_VIEW_TTL_DAYS."""
    cutoff = now - timedelta(days=RESIDENCE_VIEW_TTL_DAYS)
    deleted, _ = ResidenceView.objects.filter(viewed_at__lt=cutoff).delete()
    if deleted:
        logger.info("residence_view_ttl_deleted", deleted=deleted, cutoff=cutoff.isoformat())
    return deleted
