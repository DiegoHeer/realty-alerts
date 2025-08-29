from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django_celery_beat.models import PeriodicTask
from loguru import logger

from ui.models import RealtyQuery


@receiver([post_save], sender=RealtyQuery)
def create_and_toggle_periodic_task(instance: RealtyQuery, **kwargs) -> None:
    periodic_task, created = PeriodicTask.objects.get_or_create(
        name=instance.name,
        defaults={
            "task": "ui.tasks.scrape_and_notify",
            "crontab": instance.cron_schedule,
            "args": instance.name,
        },
    )

    if created:
        logger.info(f"Created periodic task for query '{instance.name}'")

    _toggle_periodic_task(periodic_task, enable=instance.enabled)


def _toggle_periodic_task(periodic_task: PeriodicTask, enable: bool) -> None:
    periodic_task.enabled = enable
    periodic_task.save()


@receiver([post_delete], sender=RealtyQuery)
def delete_periodic_task(instance: RealtyQuery, **kwargs) -> None:
    try:
        periodic_task = PeriodicTask.objects.get(name=instance.name)
    except RealtyQuery.DoesNotExist:
        return

    periodic_task.delete()
    logger.info(f"Deleted periodic task for query '{instance.name}'")
