import factory

from ui.models import RealtyQuery, RealtyResult


class RealtyQueryFactory(factory.django.DjangoModelFactory):
    name = factory.declarations.Sequence(lambda n: f"Query {n}")
    ntfy_topic = "test-topic"
    cron_schedule = "* * * * *"
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
