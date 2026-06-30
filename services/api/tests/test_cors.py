"""CORS preflight behaviour for browser clients (web build, local dev).

Native mobile builds don't enforce CORS; the web target does. allauth headless
carries JWTs in the Authorization header (no cookies), so credentials stay off.

local.py / ci.py run with CORS_ALLOW_ALL_ORIGINS=True, so these tests pin the
controlled prod policy (sourced from base.py to avoid drift) via the settings
fixture, making them independent of the active settings module.
"""

import pytest
from django.test import Client

from realty_api.settings import base as base_settings


@pytest.fixture
def controlled_cors(settings):
    """Pin base.py's controlled policy, with a sample deployed web origin."""
    settings.CORS_ALLOW_ALL_ORIGINS = False
    settings.CORS_ALLOWED_ORIGINS = ["https://app.realty-ai.nl"]
    settings.CORS_ALLOWED_ORIGIN_REGEXES = base_settings.CORS_ALLOWED_ORIGIN_REGEXES
    settings.CORS_ALLOW_HEADERS = base_settings.CORS_ALLOW_HEADERS


@pytest.fixture
def permissive_cors(settings):
    settings.CORS_ALLOW_ALL_ORIGINS = True


def _preflight(origin: str, request_headers: str = "content-type"):
    return Client().options(
        "/_allauth/app/v1/auth/signup",
        HTTP_ORIGIN=origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS=request_headers,
    )


@pytest.mark.usefixtures("controlled_cors")
class TestControlledCors:
    """base.py policy: localhost (any port) + configured origins, others denied."""

    def test_localhost_any_port_is_allowed(self):
        response = _preflight("http://localhost:8088")

        assert response.headers.get("access-control-allow-origin") == "http://localhost:8088"

    def test_localhost_other_port_is_allowed(self):
        response = _preflight("http://localhost:19006")

        assert response.headers.get("access-control-allow-origin") == "http://localhost:19006"

    def test_configured_origin_is_allowed(self):
        response = _preflight("https://app.realty-ai.nl")

        assert response.headers.get("access-control-allow-origin") == "https://app.realty-ai.nl"

    def test_session_token_header_is_allowed(self):
        response = _preflight("http://localhost:8088", request_headers="content-type,x-session-token")

        allowed = response.headers.get("access-control-allow-headers", "").lower()
        assert "x-session-token" in allowed

    def test_unknown_origin_is_denied(self):
        response = _preflight("https://evil.example.com")

        assert response.headers.get("access-control-allow-origin") is None


@pytest.mark.usefixtures("permissive_cors")
class TestPermissiveCors:
    """local.py / ci.py policy: any origin echoed back as a wildcard."""

    def test_any_origin_is_allowed(self):
        response = _preflight("https://anything.example.com")

        assert response.headers.get("access-control-allow-origin") == "*"
