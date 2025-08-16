import pytest
from django_celery_beat.models import IntervalSchedule, PeriodicTask
from pytest_mock import MockFixture

from ui.tests.factories import RealtyQueryFactory


@pytest.fixture
def realty_query(db):
    return RealtyQueryFactory()


@pytest.fixture
def periodic_task(db) -> PeriodicTask:
    interval = IntervalSchedule.objects.create(every=1, period=IntervalSchedule.HOURS)
    return PeriodicTask.objects.create(name="test task", task="ui.tasks.scrape_and_notify", interval=interval)


def test_create_periodic_task__success(db, mocker: MockFixture):
    mock_logger = mocker.patch("ui.signals.logger.info")

    realty_query = RealtyQueryFactory()

    assert PeriodicTask.objects.count() == 1

    periodic_task = PeriodicTask.objects.first()
    assert periodic_task is not None
    assert periodic_task.name == realty_query.name
    assert periodic_task.task == "ui.tasks.scrape_and_notify"
    assert periodic_task.crontab == realty_query.cron_schedule
    assert periodic_task.args == realty_query.name

    assert mock_logger.call_count == 1
    assert mock_logger.call_args.args[0] == f"Created periodic task for query '{realty_query.name}'"


def test_create_periodic_task__already_exists(db, mocker: MockFixture, periodic_task: PeriodicTask):
    mock_logger = mocker.patch("ui.signals.logger.info")

    RealtyQueryFactory(name=periodic_task.name)

    assert PeriodicTask.objects.count() == 1
    assert mock_logger.call_count == 0


def test_delete_periodic_task__success(db, mocker: MockFixture, periodic_task: PeriodicTask):
    mock_logger = mocker.patch("ui.signals.logger.info")

    realty_query = RealtyQueryFactory(name=periodic_task.name)
    realty_query.delete()

    assert PeriodicTask.objects.count() == 0
    assert mock_logger.call_count == 1
    assert mock_logger.call_args.args[0] == f"Deleted periodic task for query '{realty_query.name}'"
