from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from pydantic import ValidationError

from scraping.models import (
    DetailScrapeRun,
    DetailScrapeRunStatus,
    Listing,
    ListingStatus,
)
from scraping.schemas import DetailListingIn, DetailResultIn, DetailResultStatus
from tests.factories import ListingFactory

pytestmark = pytest.mark.django_db


def test_detail_result_in_success_with_detail():
    payload = DetailResultIn(
        status=DetailResultStatus.SUCCESS,
        started_at="2026-05-13T10:00:00Z",
        finished_at="2026-05-13T10:01:00Z",
        detail=DetailListingIn(price="€ 350.000 k.k.", status="new"),
    )
    assert payload.detail is not None


def test_detail_result_in_success_rejects_missing_detail():
    with pytest.raises(ValidationError, match="detail is required"):
        DetailResultIn(
            status=DetailResultStatus.SUCCESS,
            started_at="2026-05-13T10:00:00Z",
            finished_at="2026-05-13T10:01:00Z",
        )


def test_detail_result_in_failed_allows_no_detail():
    payload = DetailResultIn(
        status=DetailResultStatus.FAILED,
        started_at="2026-05-13T10:00:00Z",
        finished_at="2026-05-13T10:01:00Z",
        error_message="Bot detected",
    )
    assert payload.detail is None
    assert payload.error_message == "Bot detected"


def _detail_payload(*, status="success", error_message=None, detail=None):
    started = datetime.now(UTC) - timedelta(minutes=1)
    finished = datetime.now(UTC)
    payload = {
        "status": status,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
    }
    if error_message:
        payload["error_message"] = error_message
    if detail:
        payload["detail"] = detail
    else:
        if status == "success":
            payload["detail"] = {
                "price": "€ 350.000 k.k.",
                "status": "new",
                "surface_area_m2": 85,
                "bedroom_count": 2,
            }
    return payload


def test_detail_result_success_updates_listing_and_run(client, api_key_headers):
    listing = cast(Listing, ListingFactory())
    run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    payload = _detail_payload(status="success")

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == DetailScrapeRunStatus.SUCCESS.value
    assert body["listing_id"] == listing.pk
    assert body["finished_at"] is not None
    assert body["duration_seconds"] is not None

    listing.refresh_from_db()
    assert listing.detail_scraped_at is not None
    assert listing.price == "€ 350.000 k.k."
    assert listing.status == ListingStatus.NEW

    run.refresh_from_db()
    assert run.status == DetailScrapeRunStatus.SUCCESS
    assert run.finished_at is not None
    assert run.duration_seconds is not None


def test_detail_result_failed_updates_run_only(client, api_key_headers):
    listing = cast(Listing, ListingFactory())
    run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    payload = _detail_payload(status="failed", error_message="Bot detected")

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == DetailScrapeRunStatus.FAILED.value

    run.refresh_from_db()
    assert run.status == DetailScrapeRunStatus.FAILED
    assert run.error_message == "Bot detected"

    listing.refresh_from_db()
    assert listing.detail_scraped_at is None


def test_detail_result_404_when_no_dispatched_run(client, api_key_headers):
    listing = cast(Listing, ListingFactory())
    payload = _detail_payload(status="success")

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 404


def test_detail_result_404_when_listing_not_found(client, api_key_headers):
    payload = _detail_payload(status="success")

    response = client.patch(
        "/internal/v1/listings/99999/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 404


def test_detail_result_requires_api_key(client):
    payload = _detail_payload(status="success")

    response = client.patch("/internal/v1/listings/1/detail", json=payload)

    assert response.status_code == 401


def test_detail_result_correlates_to_latest_dispatched_run(client, api_key_headers):
    listing = cast(Listing, ListingFactory())
    old_run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    new_run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    payload = _detail_payload(status="success")

    response = client.patch(
        f"/internal/v1/listings/{listing.pk}/detail",
        json=payload,
        headers=api_key_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == new_run.pk

    new_run.refresh_from_db()
    assert new_run.status == DetailScrapeRunStatus.SUCCESS

    old_run.refresh_from_db()
    assert old_run.status == DetailScrapeRunStatus.DISPATCHED
