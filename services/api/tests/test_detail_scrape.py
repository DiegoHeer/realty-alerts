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
