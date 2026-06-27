import pytest
from django.test import Client
from loguru import logger


@pytest.fixture
def log_messages():
    messages: list[str] = []
    sink_id = logger.add(messages.append, format="{message}", level="INFO")
    yield messages
    logger.remove(sink_id)


@pytest.mark.django_db
class TestVersioningMiddleware:
    def test_logs_api_version_and_app_version(self, log_messages):
        Client().get("/v1/meta?api_version=2", HTTP_X_APP_VERSION="1.4.0")
        joined = "".join(log_messages)
        assert "version=2" in joined
        assert "1.4.0" in joined
        assert "/v1/meta" in joined

    def test_no_deprecation_headers_when_lifecycle_empty(self, settings):
        settings.API_VERSION_LIFECYCLE = {}
        response = Client().get("/v1/meta?api_version=1")
        assert "Deprecation" not in response.headers
        assert "Sunset" not in response.headers

    def test_deprecation_headers_emitted_for_configured_version(self, settings):
        settings.API_VERSION_LIFECYCLE = {1: {"deprecation": "true", "sunset": "Wed, 01 Jan 2025 00:00:00 GMT"}}
        deprecated = Client().get("/v1/meta?api_version=1")
        assert deprecated.headers["Deprecation"] == "true"
        assert deprecated.headers["Sunset"] == "Wed, 01 Jan 2025 00:00:00 GMT"
        current = Client().get("/v1/meta?api_version=2")
        assert "Deprecation" not in current.headers

    def test_app_version_never_changes_response(self, settings):
        settings.API_VERSION_LIFECYCLE = {}
        plain = Client().get("/v1/meta?api_version=2")
        with_app = Client().get("/v1/meta?api_version=2", HTTP_X_APP_VERSION="9.9.9")
        assert plain.content == with_app.content
        assert "Deprecation" not in with_app.headers
