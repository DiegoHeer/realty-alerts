import json
from pathlib import Path

import pytest

from models import RealtyQuery
from queries import load_queries


@pytest.fixture
def correct_queries_dir() -> Path:
    return Path(__file__).resolve().parents[0] / "data" / "correct_queries"


@pytest.fixture
def incorrect_queries_dir() -> Path:
    return Path(__file__).resolve().parents[0] / "data" / "incorrect_queries"


@pytest.fixture
def no_queries_dir() -> Path:
    return Path(__file__).resolve().parents[0] / "data" / "no_queries"


@pytest.fixture
def query_schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "query_schema.json"


@pytest.fixture
def query_schema(query_schema_path) -> dict:
    with open(query_schema_path) as file:
        return json.load(file)


def test_load_queries__success(correct_queries_dir):
    queries = load_queries(correct_queries_dir)

    assert queries[0].name == "Correct Query 1"
    assert queries[0].cron_schedule == "5 4 * * *"
    assert queries[0].query_url == "https://www.funda.nl/zoeken/koop"
    assert queries[0].max_listing_page_number == 3
    assert queries[0].notify_if_no_new_listing is False

    assert queries[1].name == "Correct Query 2"
    assert queries[1].cron_schedule == "0 22 * * 1-5"
    assert queries[1].query_url == "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D"
    assert queries[1].max_listing_page_number == 5
    assert queries[1].notify_if_no_new_listing is True


def test_load_queries__incorrect_queries(incorrect_queries_dir):
    with pytest.raises(ValueError) as exc:
        load_queries(incorrect_queries_dir)

    assert "2 validation errors for RealtyQuery" in str(exc.value)
    assert "The cron schedule 0 test * * 1-5 is invalid. Please place a valid crontab." in str(exc.value)
    assert "The query url https://incorrect-website.nl has an invalid domain" in str(exc.value)


def test_load_queries__no_queries(no_queries_dir):
    with pytest.raises(FileNotFoundError) as exc:
        load_queries(no_queries_dir)

    assert "There are no query files" in str(exc.value)


def test_query_schema(query_schema_path, query_schema):
    pydantic_query_schema = RealtyQuery.model_json_schema()

    if not query_schema == pydantic_query_schema:
        with open(query_schema_path, "w") as file:
            json.dump(pydantic_query_schema, file, indent=2)

        raise ValueError("Query json schema is not equal to pydantic json schema. Query schema has been updated.")
