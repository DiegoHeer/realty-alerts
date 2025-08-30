import factory
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from ui.models import RealtyQuery, RealtyResult


class CrontabScheduleFactory(factory.django.DjangoModelFactory):
    minute = "0"
    hour = "0"
    day_of_month = "*"
    month_of_year = "*"
    day_of_week = "*"

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = CrontabSchedule


class PeriodicTaskFactory(factory.django.DjangoModelFactory):
    name = factory.declarations.Sequence(lambda n: f"Periodic Task {n}")
    task = "ui.tasks.scrape_and_notify"
    crontab = factory.declarations.SubFactory(CrontabScheduleFactory)
    args = factory.declarations.Sequence(lambda n: f"['Query {n}']")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = PeriodicTask


class RealtyQueryFactory(factory.django.DjangoModelFactory):
    name = factory.declarations.Sequence(lambda n: f"Query {n}")
    ntfy_topic = "test-topic"
    periodic_task = factory.declarations.SubFactory(PeriodicTaskFactory)
    query_url = factory.declarations.Sequence(lambda n: f"https://www.funda.nl/{n}")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = RealtyQuery


class RealtyResultFactory(factory.django.DjangoModelFactory):
    detail_url = factory.declarations.Sequence(lambda n: f"https://www.funda.nl/house-{n}")
    query = factory.declarations.SubFactory(RealtyQueryFactory)
    title = factory.declarations.Sequence(lambda n: f"House {n}")
    price = "€350.000,00"
    image_url = factory.declarations.Sequence(lambda n: f"https://image-cdn.com/{n}")

    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = RealtyResult
