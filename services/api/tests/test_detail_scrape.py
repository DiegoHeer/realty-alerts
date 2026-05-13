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
