from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import patch

import pytest

from scraping.models import DetailScrapeRun, DetailScrapeRunStatus, Listing, ListingStatus
from tests.factories import ListingFactory


pytestmark = pytest.mark.django_db


def test_dispatches_listings_nulls_first_then_oldest():
    now = datetime.now(UTC)
    old = cast(Listing, ListingFactory(detail_scraped_at=now - timedelta(days=30)))
    recent = cast(Listing, ListingFactory(detail_scraped_at=now - timedelta(days=1)))
    never = cast(Listing, ListingFactory(detail_scraped_at=None))

    with patch("scraping.tasks.dispatch_detail_scrape.delay") as mock_delay:
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 3
    dispatched_ids = [call.kwargs["listing_id"] for call in mock_delay.call_args_list]
    assert dispatched_ids == [never.pk, old.pk, recent.pk]


def test_excludes_sold_residences():
    cast(Listing, ListingFactory(residence__current_status=ListingStatus.SOLD))
    active = cast(Listing, ListingFactory(residence__current_status=ListingStatus.NEW))

    with patch("scraping.tasks.dispatch_detail_scrape.delay"):
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 1
    assert DetailScrapeRun.objects.first().listing_id == active.pk


def test_excludes_sale_pending_residences():
    cast(Listing, ListingFactory(residence__current_status=ListingStatus.SALE_PENDING))
    active = cast(Listing, ListingFactory(residence__current_status=ListingStatus.NEW))

    with patch("scraping.tasks.dispatch_detail_scrape.delay"):
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 1
    assert DetailScrapeRun.objects.first().listing_id == active.pk


def test_excludes_listings_without_residence():
    cast(Listing, ListingFactory(residence=None))
    with_residence = cast(Listing, ListingFactory())

    with patch("scraping.tasks.dispatch_detail_scrape.delay"):
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 1
    assert DetailScrapeRun.objects.first().listing_id == with_residence.pk


def test_excludes_listings_with_inflight_dispatch():
    inflight = cast(Listing, ListingFactory())
    DetailScrapeRun.objects.create(
        listing=inflight,
        website=inflight.website,
        status=DetailScrapeRunStatus.DISPATCHED,
    )
    eligible = cast(Listing, ListingFactory())

    with patch("scraping.tasks.dispatch_detail_scrape.delay"):
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 1
    new_runs = DetailScrapeRun.objects.filter(listing=eligible)
    assert new_runs.count() == 1


def test_limits_to_100_listings():
    ListingFactory.create_batch(105)

    with patch("scraping.tasks.dispatch_detail_scrape.delay") as mock_delay:
        from scraping.tasks import dispatch_stale_detail_scrapes

        result = dispatch_stale_detail_scrapes()

    assert result == 100
    assert mock_delay.call_count == 100


def test_returns_zero_when_no_eligible_listings():
    from scraping.tasks import dispatch_stale_detail_scrapes

    result = dispatch_stale_detail_scrapes()

    assert result == 0
    assert DetailScrapeRun.objects.count() == 0
