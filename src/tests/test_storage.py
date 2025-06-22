from time import sleep

import pytest
from peewee import SqliteDatabase

from models import QueryResult
from storage import QueryResultsORM, get_new_query_results, save_query_results


@pytest.fixture(autouse=True)
def setup_test_db():
    test_db = SqliteDatabase(":memory:")
    test_db.bind([QueryResultsORM], bind_refs=False, bind_backrefs=False)
    test_db.connect()
    test_db.create_tables([QueryResultsORM])

    yield

    test_db.drop_tables([QueryResultsORM])
    test_db.close()


@pytest.fixture
def query_results() -> list[QueryResult]:
    return [
        QueryResult(
            detail_url="https://test_1.com",
            query_name="Test Query 1",
            title="test 1",
            price="€777",
            image_url="https://image_1.com",
        ),
        QueryResult(
            detail_url="https://test_2.com",
            query_name="Test Query 2",
            title="test 2",
            price="€865700",
            image_url="https://image_2.com",
        ),
    ]


@pytest.fixture
def new_query_result() -> QueryResult:
    return QueryResult(
        detail_url="https://test_1.com",
        query_name="New Query",
        title="new test",
        price="€1000000",
        image_url="https://new-image.com",
    )


def test_save_query_result_to_db__success(query_results: list[QueryResult]):
    save_query_results(query_results)

    assert QueryResultsORM.select().count() == 2

    query_result_1 = query_results[0]
    row = QueryResultsORM.get(QueryResultsORM.detail_url == query_result_1.detail_url)
    assert row.id == 1
    assert row.detail_url == query_result_1.detail_url
    assert row.title == query_result_1.title
    assert row.price == query_result_1.price
    assert row.image_url == query_result_1.image_url
    assert row.created_at is not None
    assert row.updated_at is not None


def test_save_query_result_to_db__duplicate(query_results: list[QueryResult], new_query_result: QueryResult):
    save_query_results(query_results)
    sleep(0.1)
    save_query_results([new_query_result])

    assert QueryResultsORM.select().count() == 2

    query_result_1 = query_results[0]
    row = QueryResultsORM.get(QueryResultsORM.detail_url == query_result_1.detail_url)
    assert row.id == 1
    assert row.title == new_query_result.title
    assert row.updated_at > row.created_at


def test_get_new_query_results__success(query_results: list[QueryResult]):
    save_query_results(query_results)

    new_query_results = get_new_query_results()

    assert len(new_query_results) == 2


def test_get_new_query_results__duplicate(query_results: list[QueryResult]):
    save_query_results(query_results)
    save_query_results(query_results)

    new_query_results = get_new_query_results()

    assert len(new_query_results) == 0
