from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from scraping.models import Listing, ScrapeRun, ScrapeRunStatus, Website
from tests.factories import ListingFactory, ScrapeRunFactory

pytestmark = pytest.mark.django_db


def test_last_successful_run_no_runs(client, api_key_headers):
    response = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers=api_key_headers)
    assert response.status_code == 200
    assert response.json() is None


def test_last_successful_returns_latest_success(client, api_key_headers):
    ScrapeRunFactory(
        website=Website.FUNDA, status=ScrapeRunStatus.SUCCESS, started_at=datetime.now(UTC) - timedelta(hours=2)
    )
    latest = cast(
        ScrapeRun,
        ScrapeRunFactory(
            website=Website.FUNDA, status=ScrapeRunStatus.SUCCESS, started_at=datetime.now(UTC) - timedelta(minutes=10)
        ),
    )
    ScrapeRunFactory(
        website=Website.FUNDA, status=ScrapeRunStatus.FAILED, started_at=datetime.now(UTC) - timedelta(minutes=1)
    )

    response = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers=api_key_headers)
    assert response.status_code == 200
    assert response.json()["id"] == latest.pk


def test_active_runs_lists_only_running(client, api_key_headers):
    ScrapeRunFactory(status=ScrapeRunStatus.SUCCESS)
    ScrapeRunFactory(status=ScrapeRunStatus.FAILED)
    running = cast(ScrapeRun, ScrapeRunFactory(status=ScrapeRunStatus.RUNNING, finished_at=None))

    response = client.get("/internal/v1/scrape-runs/active", headers=api_key_headers)
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == running.pk


def test_submit_results_creates_run_and_listings(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[
            listing_payload("https://example.com/listing/1"),
            listing_payload("https://example.com/listing/2"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["listings_new"] == 2
    assert body["status"] == ScrapeRunStatus.SUCCESS.value
    assert ScrapeRun.objects.count() == 1
    assert Listing.objects.count() == 2


def test_submit_results_dedups_existing_listings(client, api_key_headers, scrape_payload, listing_payload):
    ListingFactory(detail_url="https://example.com/listing/1")
    payload = scrape_payload(
        listings=[
            listing_payload("https://example.com/listing/1"),
            listing_payload("https://example.com/listing/2"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["listings_new"] == 1
    assert Listing.objects.count() == 2


def test_submit_results_rejects_inverted_timestamps(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[])
    payload["started_at"], payload["finished_at"] = payload["finished_at"], payload["started_at"]

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422


def test_submit_results_marks_run_failed_when_error_message(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[], error_message="boom")

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == ScrapeRunStatus.FAILED.value


def test_internal_endpoints_require_api_key(client):
    no_key = client.get(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful")
    wrong_key = client.get(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful", headers={"X-API-Key": "wrong"}
    )
    assert no_key.status_code == 401
    assert wrong_key.status_code == 401
