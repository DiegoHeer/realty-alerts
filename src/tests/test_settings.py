import pytest
from celery.schedules import crontab

from enums import HouseTypes, Websites
from models import RealtyFilters, RealtyQuery
from settings import SETTINGS, CeleryConfig


@pytest.fixture
def realty_queries() -> list[RealtyQuery]:
    return [
        RealtyQuery(
            cron_schedule="* * * * *",
            website=Websites.FUNDA,
            filters=RealtyFilters(
                house_type=HouseTypes.WOONHUIS,
            ),
        ),
        RealtyQuery(
            cron_schedule="*/2 4 6 * 1-5",
            website=Websites.FUNDA,
            filters=RealtyFilters(
                house_type=HouseTypes.APPARTEMENT,
            ),
        ),
    ]


def test_celery_config(realty_queries: list[RealtyQuery]):
    celery_config = CeleryConfig(realty_queries)

    assert celery_config.broker_url == SETTINGS.redis_url
    assert len(celery_config.beat_schedule) == 2
    assert celery_config.beat_schedule["0"]["task"] == "tasks.main"
    assert celery_config.beat_schedule["0"]["schedule"] == crontab()
    assert celery_config.beat_schedule["0"]["args"][0] == realty_queries[0].model_dump()
