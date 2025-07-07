import pytest
from pytest_mock import MockFixture

from models import QueryResult, RealtyQuery
from notifications import _build_headers, _build_message, notify_about_new_results, notify_about_successful_startup


@pytest.fixture
def sample_query_result() -> QueryResult:
    return QueryResult(
        title="Charming House",
        query_name="Houses in Amsterdam",
        detail_url="https://www.funda.nl/listing/123",
        price="€310000 k.k.",
        image_url="https://example-image.com",
    )


@pytest.fixture
def ntfy_url() -> str:
    return "https://ntfy.sh/amsterdam-houses"


@pytest.fixture
def sample_realty_query() -> RealtyQuery:
    return RealtyQuery(
        name="Houses in Amsterdam",
        ntfy_topic="amsterdam-houses",
        cron_schedule="* * * * *",
        query_url="https://www.funda.nl/houses?city=amsterdam",
    )


def test_build_message(sample_query_result: QueryResult):
    message = _build_message(sample_query_result)

    assert message == "New house for sale. Price: €310000 k.k."


def test_build_headers(sample_query_result: QueryResult):
    headers = _build_headers(sample_query_result)

    assert headers["Priority"] == "urgent"
    assert headers["Tags"] == "house, rotating_light"
    assert headers["Title"] == "Houses in Amsterdam -> Charming House"
    assert headers["Click"] == "https://www.funda.nl/listing/123"
    assert headers["Attach"] == "https://example-image.com"


def test_send_notifications__success(mocker: MockFixture, sample_query_result: QueryResult, ntfy_url: str):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))
    mock_logger = mocker.patch("notifications.LOGGER")

    notify_about_new_results(ntfy_url, query_results=[sample_query_result])

    assert mock_post.call_count == 1
    assert mock_logger.info.call_count == 1


def test_send_notifications__failure(mocker: MockFixture, sample_query_result: QueryResult, ntfy_url: str):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=False, status_code=500))
    mock_logger = mocker.patch("notifications.LOGGER")

    notify_about_new_results(ntfy_url, query_results=[sample_query_result])

    assert mock_post.call_count == 1
    assert mock_logger.error.call_count == 1
    assert "Failed to send notification" in mock_logger.error.call_args[0][0]
    assert "Status code: 500" in mock_logger.error.call_args[0][0]


def test_notify_about_successful_startup(mocker: MockFixture, sample_realty_query: RealtyQuery):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))
    mock_logger = mocker.patch("notifications.LOGGER")

    notify_about_successful_startup([sample_realty_query])

    assert mock_post.call_count == 1
    assert mock_logger.info.call_count == 2


def test_notify_about_successful_startup__no_notification(mocker: MockFixture, sample_realty_query: RealtyQuery):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))
    mock_logger = mocker.patch("notifications.LOGGER")

    sample_realty_query.notify_startup_of_app = False
    notify_about_successful_startup([sample_realty_query])

    assert mock_post.call_count == 0
    assert mock_logger.info.call_count == 2
