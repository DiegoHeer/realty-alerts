import pytest
from pytest_mock import MockFixture

from models import QueryResult
from notifications import _build_headers, _build_message, send_notifications


@pytest.fixture
def sample_query_result() -> QueryResult:
    return QueryResult(
        title="Charming House",
        query_name="Houses in Amsterdam",
        detail_url="https://example.com/listing/123",
        price="€310000 k.k.",
        image_url="https://example-image.com",
    )


def test_build_message(sample_query_result):
    message = _build_message(sample_query_result)

    assert message == "New house for sale. Price: €310000 k.k."


def test_build_headers(sample_query_result):
    headers = _build_headers(sample_query_result)

    assert headers["Priority"] == "urgent"
    assert headers["Tags"] == "house, rotating_light"
    assert headers["Title"] == "Houses in Amsterdam -> Charming House"
    assert headers["Click"] == "https://example.com/listing/123"
    assert headers["Attach"] == "https://example-image.com"


def test_send_notifications__success(mocker: MockFixture, sample_query_result):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))
    mock_logger = mocker.patch("notifications.LOGGER")

    send_notifications([sample_query_result])

    assert mock_post.call_count == 1
    assert mock_logger.info.call_count == 1


def test_send_notifications__failure(mocker: MockFixture, sample_query_result):
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=False, status_code=500))
    mock_logger = mocker.patch("notifications.LOGGER")

    send_notifications([sample_query_result])

    assert mock_post.call_count == 1
    assert mock_logger.error.call_count == 1
    assert "Failed to send notification" in mock_logger.error.call_args[0][0]
    assert "Status code: 500" in mock_logger.error.call_args[0][0]
