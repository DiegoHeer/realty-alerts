import pytest
from celery.schedules import crontab
from pytest_mock import MockerFixture

from models import RealtyQuery
from scheduler import CeleryConfig
from settings import SETTINGS


@pytest.fixture
def realty_queries(mocker: MockerFixture) -> list[RealtyQuery]:
    mocker.patch("requests.post", return_value=mocker.MagicMock(ok=True))

    return [
        RealtyQuery(
            name="Query 1",
            ntfy_topic="topic_1",
            cron_schedule="* * * * *",
            query_url="https://www.funda.nl/zoeken/koop",
        ),
        RealtyQuery(
            name="Query 2",
            ntfy_topic="topic_2",
            cron_schedule="*/2 4 6 * 1-5",
            query_url="https://www.funda.nl/zoeken/koop",
        ),
    ]


def test_celery_config(realty_queries: list[RealtyQuery]):
    celery_config = CeleryConfig(realty_queries)

    assert celery_config.broker_url == SETTINGS.redis_url
    assert len(celery_config.beat_schedule) == 2
    assert celery_config.beat_schedule["0"]["task"] == "tasks.main"
    assert celery_config.beat_schedule["0"]["schedule"] == crontab()
    assert celery_config.beat_schedule["0"]["args"][0] == realty_queries[0].model_dump()
