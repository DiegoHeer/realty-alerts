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


from unittest.mock import MagicMock, patch
from django.contrib import messages
from scraping.models import Residence
from tests.factories import ResidenceFactory


def test_scrape_details_action_dispatches_tasks():
    from scraping.admin import scrape_details

    listing1 = cast(Listing, ListingFactory())
    listing2 = cast(Listing, ListingFactory())
    queryset = Listing.objects.filter(pk__in=[listing1.pk, listing2.pk])

    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.dispatch_detail_scrape.delay") as mock_delay:
        scrape_details(modeladmin, request, queryset)

    assert mock_delay.call_count == 2
    assert DetailScrapeRun.objects.count() == 2
    assert DetailScrapeRun.objects.filter(status=DetailScrapeRunStatus.DISPATCHED).count() == 2

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert len(success_calls) == 1
    assert "2" in success_calls[0].args[1]


def test_scrape_residence_details_dispatches_for_all_linked_listings():
    from scraping.admin import scrape_residence_details

    residence = cast(Residence, ResidenceFactory())
    listing1 = cast(Listing, ListingFactory(residence=residence, website=Website.FUNDA))
    listing2 = cast(Listing, ListingFactory(residence=residence, website=Website.PARARIUS))
    queryset = Residence.objects.filter(pk=residence.pk)

    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.dispatch_detail_scrape.delay") as mock_delay:
        scrape_residence_details(modeladmin, request, queryset)

    assert mock_delay.call_count == 2
    assert DetailScrapeRun.objects.count() == 2

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert len(success_calls) == 1
    assert "2 listing(s)" in success_calls[0].args[1]
    assert "1 residence(s)" in success_calls[0].args[1]


def test_scrape_residence_details_handles_multiple_residences():
    from scraping.admin import scrape_residence_details

    r1 = cast(Residence, ResidenceFactory())
    r2 = cast(Residence, ResidenceFactory())
    cast(Listing, ListingFactory(residence=r1))
    cast(Listing, ListingFactory(residence=r2))
    cast(Listing, ListingFactory(residence=r2))
    queryset = Residence.objects.filter(pk__in=[r1.pk, r2.pk])

    modeladmin = MagicMock()
    request = MagicMock()

    with patch("scraping.admin.dispatch_detail_scrape.delay") as mock_delay:
        scrape_residence_details(modeladmin, request, queryset)

    assert mock_delay.call_count == 3
    assert DetailScrapeRun.objects.count() == 3

    success_calls = [c for c in modeladmin.message_user.call_args_list if c.args[2] == messages.SUCCESS]
    assert "3 listing(s)" in success_calls[0].args[1]
    assert "2 residence(s)" in success_calls[0].args[1]
