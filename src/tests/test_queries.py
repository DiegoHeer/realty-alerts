from pathlib import Path

import pytest

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


def test_load_queries__success(correct_queries_dir):
    queries = load_queries(correct_queries_dir)

    assert queries[0].cron_schedule == "5 4 * * *"
    assert queries[0].website == "funda"
    assert queries[0].filters.house_type == "Woonhuis"

    assert queries[1].cron_schedule == "0 22 * * 1-5"
    assert queries[1].website == "funda"
    assert queries[1].filters.house_type == "Appartement"


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
