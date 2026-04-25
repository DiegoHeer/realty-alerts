from datetime import UTC, datetime, timedelta

import pytest
from django.conf import settings

from scraping.models import Listing, ScrapeRun, ScrapeRunStatus, Website
from tests.factories import ListingFactory, ScrapeRunFactory

HEADERS = {"X-API-Key": settings.INTERNAL_API_KEY}


def _payload(listings=None, error_message=None) -> dict:
    started = datetime.now(UTC) - timedelta(minutes=5)
    finished = datetime.now(UTC)
    return {
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "error_message": error_message,
        "listings": listings or [],
    }


def _listing(detail_url: str = "https://example.com/listing/new") -> dict:
    return {
        "website": Website.FUNDA.value,
        "detail_url": detail_url,
        "title": "Cozy apartment",
        "price": "€ 350.000 k.k.",
        "city": "Amsterdam",
        "property_type": "apartment",
        "bedrooms": 2,
        "area_sqm": 70.0,
        "image_url": "https://example.com/img.jpg",
    }


@pytest.mark.django_db
def test_last_successful_run_no_runs(client):
    response = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers=HEADERS)
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.django_db
def test_last_successful_returns_latest_success(client):
    ScrapeRunFactory(
        website=Website.FUNDA, status=ScrapeRunStatus.SUCCESS, started_at=datetime.now(UTC) - timedelta(hours=2)
    )
    latest = ScrapeRunFactory(
        website=Website.FUNDA, status=ScrapeRunStatus.SUCCESS, started_at=datetime.now(UTC) - timedelta(minutes=10)
    )
    ScrapeRunFactory(
        website=Website.FUNDA, status=ScrapeRunStatus.FAILED, started_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    response = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["id"] == latest.id


@pytest.mark.django_db
def test_active_runs_lists_only_running(client):
    ScrapeRunFactory(status=ScrapeRunStatus.SUCCESS)
    ScrapeRunFactory(status=ScrapeRunStatus.FAILED)
    running = ScrapeRunFactory(status=ScrapeRunStatus.RUNNING, finished_at=None)

    response = client.get("/internal/v1/scrape-runs/active", headers=HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == running.id


@pytest.mark.django_db
def test_submit_results_creates_run_and_listings(client):
    payload = _payload(listings=[_listing("https://example.com/listing/1"), _listing("https://example.com/listing/2")])

    response = client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["listings_new"] == 2
    assert body["status"] == ScrapeRunStatus.SUCCESS.value
    assert ScrapeRun.objects.count() == 1
    assert Listing.objects.count() == 2


@pytest.mark.django_db
def test_submit_results_dedups_existing_listings(client):
    ListingFactory(detail_url="https://example.com/listing/1")
    payload = _payload(listings=[_listing("https://example.com/listing/1"), _listing("https://example.com/listing/2")])

    response = client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=HEADERS)

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["listings_new"] == 1
    assert Listing.objects.count() == 2


@pytest.mark.django_db
def test_submit_results_marks_run_failed_when_error_message(client):
    payload = _payload(listings=[], error_message="boom")

    response = client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == ScrapeRunStatus.FAILED.value


@pytest.mark.django_db
def test_internal_endpoints_require_api_key(client):
    no_key = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful")
    wrong_key = client.get(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers={"X-API-Key": "wrong"}
    )
    assert no_key.status_code == 401
    assert wrong_key.status_code == 401
