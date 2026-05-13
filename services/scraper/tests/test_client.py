import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from scraper.client import BackendClient
from scraper.enums import DetailResultStatus, ListingStatus
from scraper.models import DetailListing

BASE_URL = "http://test-api"
API_KEY = "testkey"

_STARTED = datetime(2026, 5, 13, 10, 0, 0, tzinfo=UTC)
_FINISHED = _STARTED + timedelta(minutes=1)


@respx.mock
def test_submit_detail_result_patches_correct_endpoint():
    detail = DetailListing(
        price="€ 510.000,- k.k.",
        status=ListingStatus.NEW,
        surface_area_m2=95,
        bedroom_count=2,
        bathroom_count=1,
        room_count=3,
        construction_period="1991-2000",
        energy_label="A",
    )
    route = respx.patch(f"{BASE_URL}/internal/v1/listings/42/detail").mock(return_value=httpx.Response(200, json={}))

    client = BackendClient(base_url=BASE_URL, api_key=API_KEY)
    client.submit_detail_result(
        listing_id=42, status=DetailResultStatus.SUCCESS, started_at=_STARTED, finished_at=_FINISHED, detail=detail
    )

    assert route.called
    sent = route.calls.last.request
    body = json.loads(sent.content)
    assert body["status"] == "success"
    assert body["started_at"] == _STARTED.isoformat()
    assert body["finished_at"] == _FINISHED.isoformat()
    assert body["detail"]["price"] == "€ 510.000,- k.k."
    assert body["detail"]["status"] == "new"
    assert body["detail"]["surface_area_m2"] == 95


@respx.mock
def test_submit_detail_result_failed_includes_error():
    route = respx.patch(f"{BASE_URL}/internal/v1/listings/42/detail").mock(return_value=httpx.Response(200, json={}))

    client = BackendClient(base_url=BASE_URL, api_key=API_KEY)
    client.submit_detail_result(
        listing_id=42,
        status=DetailResultStatus.FAILED,
        started_at=_STARTED,
        finished_at=_FINISHED,
        error_message="Bot detected",
    )

    assert route.called
    body = json.loads(route.calls.last.request.content)
    assert body["status"] == "failed"
    assert body["error_message"] == "Bot detected"
    assert "detail" not in body


@respx.mock
def test_submit_detail_result_raises_on_non_2xx():
    respx.patch(f"{BASE_URL}/internal/v1/listings/99/detail").mock(return_value=httpx.Response(404))

    client = BackendClient(base_url=BASE_URL, api_key=API_KEY)

    with pytest.raises(httpx.HTTPStatusError):
        client.submit_detail_result(
            listing_id=99,
            status=DetailResultStatus.SUCCESS,
            started_at=_STARTED,
            finished_at=_FINISHED,
            detail=DetailListing(price="€ 100.000", status=ListingStatus.NEW),
        )
