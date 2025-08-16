import pytest
from django.core.exceptions import ValidationError

from enums import Websites
from ui.tests.factories import RealtyQueryFactory, RealtyResultFactory


def test_realty_query_model__success(db):
    query = RealtyQueryFactory()

    assert query.website == Websites.FUNDA


def test_realty_query_model__failure(db):
    with pytest.raises(ValidationError) as exc:
        RealtyQueryFactory(
            ntfy_topic="incorrect topic",
            query_url="https://incorrect-website.nl",
        )
        pass

    assert "Please correct the `ntfy_topic`" in exc.value.args[0]["ntfy_topic"][0].message
    assert "has an invalid domain" in exc.value.args[0]["query_url"][0].message


def test_realty_result_string(db):
    realty_result = RealtyResultFactory()

    assert str(realty_result) == f"{realty_result.title} ({realty_result.query.name})"
