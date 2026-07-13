from celery import shared_task
from django.utils import timezone

from accounts.cleanup import delete_stale_residence_views


@shared_task(name="accounts.cleanup_stale_residence_views")
def cleanup_stale_residence_views() -> int:
    """Hard-delete residence views past the TTL. Schedule via a PeriodicTask in Django admin."""
    return delete_stale_residence_views(now=timezone.now())
