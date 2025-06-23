from typing import Any

from celery.schedules import crontab

from models import RealtyQuery
from settings import DATA_PATH, SETTINGS


class CeleryConfig:
    broker_url = SETTINGS.redis_url
    result_backend = SETTINGS.redis_url
    timezone = SETTINGS.timezone
    enable_utc = True
    beat_schedule_filename = str(DATA_PATH / "celerybeat-schedule")

    def __init__(self, realty_queries: list[RealtyQuery]) -> None:
        self.beat_schedule = get_beat_schedule(realty_queries)


def get_beat_schedule(realty_queries: list[RealtyQuery]) -> dict[str, dict]:
    return {str(iterable): _build_query_schedule(query) for iterable, query in enumerate(realty_queries)}


def _build_query_schedule(query: RealtyQuery) -> dict[str, Any]:
    return {
        "task": "tasks.main",
        "schedule": crontab.from_string(crontab=query.cron_schedule),
        "args": [query.model_dump()],
    }
