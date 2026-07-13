from datetime import datetime

from django.db import transaction
from django.utils import timezone


def upsert_and_evict(model, *, user, residence, timestamp_field: str, timestamp: datetime, cap: int) -> None:
    timestamp = min(timestamp, timezone.now())  # clamp future timestamps to now
    with transaction.atomic():
        model.objects.update_or_create(user=user, residence=residence, defaults={timestamp_field: timestamp})
        stale_ids = list(
            model.objects.filter(user=user).order_by(f"-{timestamp_field}").values_list("id", flat=True)[cap:]
        )
        if stale_ids:
            model.objects.filter(id__in=stale_ids).delete()
