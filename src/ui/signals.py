from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask
from loguru import logger

from ui.models import RealtyQuery


@receiver([post_save], sender=RealtyQuery)
def create_periodic_task(instance: RealtyQuery, **kwargs) -> None:
    _, created = PeriodicTask.objects.get_or_create(
        name=instance.name,
        defaults={
            "task": "ui.tasks.scrape_and_notify",
            "crontab": instance.cron_schedule,
            "args": instance.name,
        },
    )

    if created:
        logger.info(f"Created periodic task for query '{instance.name}'")


@receiver([post_delete], sender=RealtyQuery)
def delete_periodic_task(instance: RealtyQuery, **kwargs) -> None:
    try:
        periodic_task = PeriodicTask.objects.get(name=instance.name)
    except RealtyQuery.DoesNotExist:
        return

    periodic_task.delete()
    logger.info(f"Deleted periodic task for query '{instance.name}'")
