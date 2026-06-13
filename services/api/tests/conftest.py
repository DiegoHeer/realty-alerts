from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode

import pytest
from django.conf import settings
from ninja.testing import TestClient

from scraping.api import api
from scraping.models import Website


class _TestClient(TestClient):
    """TestClient that sends GET data as query string parameters."""

    def get(self, path: str, data: dict | None = None, **request_params: Any) -> Any:
        if data:
            qs = urlencode({k: v for k, v in data.items() if v is not None})
            separator = "&" if "?" in path else "?"
            path = f"{path}{separator}{qs}"
            data = None
        return super().get(path, data, **request_params)


@pytest.fixture
def client() -> _TestClient:
    return _TestClient(api)


@pytest.fixture
def api_key_headers() -> dict[str, str]:
    return {"X-API-Key": settings.REALTY_API_KEY}


@pytest.fixture
def listing_payload() -> Callable[..., dict[str, Any]]:
    counter = {"n": 0}

    def _build(detail_url: str | None = None, **overrides: Any) -> dict[str, Any]:
        counter["n"] += 1
        n = counter["n"]
        data: dict[str, Any] = {
            "website": Website.FUNDA.value,
            "detail_url": detail_url or f"https://example.com/listing/{n}",
            "title": "Cozy apartment",
            "price": "€ 350.000 k.k.",
            "city": "Amsterdam",
            "image_url": "https://example.com/img.jpg",
        }
        data.update(overrides)
        return data

    return _build


@pytest.fixture
def scrape_payload() -> Callable[..., dict[str, Any]]:
    def _build(
        listings: list[dict[str, Any]] | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        started = datetime.now(UTC) - timedelta(minutes=5)
        finished = datetime.now(UTC)
        return {
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "error_message": error_message,
            "listings": listings or [],
        }

    return _build


@pytest.fixture(autouse=True)
def _eager_celery(settings):
    """Run Celery tasks synchronously in-process during tests — no broker needed."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
