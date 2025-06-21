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

    assert queries[0].cron_schedule == "5 4 * * *"
    assert queries[0].website == "funda"
    assert queries[0].filters.house_types == "Woonhuis"

    assert queries[1].cron_schedule == "0 22 * * 1-5"
    assert queries[1].website == "funda"
    assert queries[1].filters.house_types == "Appartement"


def test_load_queries__incorrect_queries(incorrect_queries_dir):
    with pytest.raises(ValueError) as exc:
        load_queries(incorrect_queries_dir)

    assert "2 validation errors for RealtyQuery" in str(exc.value)
    assert "The cron schedule 0 test * * 1-5 is invalid. Please place a valid crontab." in str(exc.value)
    assert "Input should be 'funda'" in str(exc.value)


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
