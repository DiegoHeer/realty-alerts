from datetime import UTC, datetime
from typing import cast

import pytest

from scraping.models import DetailScrapeRun, DetailScrapeRunStatus, Listing, Website
from tests.factories import ListingFactory


pytestmark = pytest.mark.django_db


def test_detail_scrape_run_creation():
    listing = cast(Listing, ListingFactory())
    run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    assert run.pk is not None
    assert run.dispatched_at is not None
    assert run.finished_at is None
    assert run.error_message is None


def test_listing_detail_scraped_at_defaults_to_none():
    listing = cast(Listing, ListingFactory())
    assert listing.detail_scraped_at is None


from scraping.schemas import ScrapeDispatchPayload, ScrapeMode


def test_scrape_dispatch_payload_defaults_to_list_mode():
    payload = ScrapeDispatchPayload(website=Website.FUNDA, run_id="abc")
    data = payload.model_dump(mode="json")
    assert data["scrape_mode"] == "list"
    assert data["detail_url"] is None
    assert data["listing_id"] is None


def test_scrape_dispatch_payload_detail_mode():
    payload = ScrapeDispatchPayload(
        website=Website.FUNDA,
        run_id="abc",
        scrape_mode=ScrapeMode.DETAIL,
        detail_url="https://funda.nl/listing/123",
        listing_id=42,
    )
    data = payload.model_dump(mode="json")
    assert data["scrape_mode"] == "detail"
    assert data["detail_url"] == "https://funda.nl/listing/123"
    assert data["listing_id"] == 42


import httpx
import respx


@respx.mock
def test_dispatch_detail_scrape_posts_to_webhook(settings):
    from scraping.tasks import dispatch_detail_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    listing = cast(Listing, ListingFactory())
    run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    route = respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))

    run_id = dispatch_detail_scrape.delay(listing_id=listing.pk, detail_scrape_run_id=run.pk).get(timeout=1)

    assert run_id and len(run_id) == 32
    assert route.called
    body = route.calls.last.request.content.decode()
    assert '"scrape_mode":"detail"' in body
    assert f'"listing_id":{listing.pk}' in body
    assert listing.url in body


def test_dispatch_detail_scrape_marks_failed_when_no_webhook(settings):
    from scraping.tasks import dispatch_detail_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = None
    listing = cast(Listing, ListingFactory())
    run = DetailScrapeRun.objects.create(
        listing=listing,
        website=listing.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )

    run_id = dispatch_detail_scrape.delay(listing_id=listing.pk, detail_scrape_run_id=run.pk).get(timeout=1)

    assert run_id and len(run_id) == 32
    run.refresh_from_db()
    assert run.status == DetailScrapeRunStatus.FAILED
    assert run.finished_at is not None
    assert "not configured" in run.error_message
