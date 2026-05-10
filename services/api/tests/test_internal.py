from datetime import UTC, datetime, timedelta
from typing import cast
from unittest import mock

import httpx
import pytest
import respx
from scraping.models import (
    BagStatus,
    Listing,
    ListingStatus,
    Residence,
    ScrapeRun,
    ScrapeRunStatus,
    Website,
)

from tests.factories import ListingFactory, ResidenceFactory, ScrapeRunFactory

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


# `transaction.on_commit` doesn't fire under pytest-django's default rolled-back
# transaction mode, so most tests below patch it to invoke the callback inline.
# The end-to-end test that asserts the full resolve_bag flow uses `transaction=True`
# to get real commits and real on-commit callbacks.
def _on_commit_inline():
    return mock.patch("scraping.api.transaction.on_commit", side_effect=lambda fn: fn())


@pytest.mark.parametrize("website", list(Website))
def test_submit_results_creates_run_and_pending_listings(
    client, api_key_headers, scrape_payload, listing_payload, website
):
    payload = scrape_payload(
        listings=[
            listing_payload(website=website.value),
            listing_payload(website=website.value),
        ]
    )

    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay") as task_delay:
        response = client.post(
            f"/internal/v1/scrape-runs/{website.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    body = response.json()
    assert body["website"] == website.value
    assert body["listings_found"] == 2
    assert body["new_listings_count"] == 2
    assert body["status"] == ScrapeRunStatus.SUCCESS.value
    assert ScrapeRun.objects.count() == 1
    assert Listing.objects.count() == 2
    # No Residence rows are created synchronously — that's the resolve_bag task's job.
    assert Residence.objects.count() == 0
    assert task_delay.call_count == 2


def test_submit_results_persists_per_portal_data_on_listing(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://funda.nl/listing/abc",
                title="Sunny duplex",
                price="€ 425.000 k.k.",
                image_url="https://cdn.example.com/abc.jpg",
                status=ListingStatus.SALE_PENDING.value,
                street="Nieuwstraat",
                house_number=42,
                postcode="1011 AA",
                city="Amsterdam",
            ),
        ],
    )

    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        response = client.post(
            f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    listing = Listing.objects.get(url="https://funda.nl/listing/abc")
    assert listing.title == "Sunny duplex"
    assert listing.price == "€ 425.000 k.k."
    assert listing.price_eur == 425_000
    assert listing.image_url == "https://cdn.example.com/abc.jpg"
    assert listing.status == ListingStatus.SALE_PENDING
    assert listing.street == "Nieuwstraat"
    assert listing.house_number == 42
    assert listing.postcode == "1011 AA"
    assert listing.city == "Amsterdam"
    assert listing.bag_status == BagStatus.PENDING
    assert listing.residence is None
    assert listing.scraped_at is not None
    assert listing.last_seen_at is not None


def test_submit_results_persists_structured_address_fields(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[
            listing_payload(
                street="Klaterweg",
                house_number=9,
                house_letter="R",
                house_number_suffix="A59",
                postcode="1271 KE",
                city="Huizen",
            )
        ],
    )

    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        response = client.post(
            f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    listing = Listing.objects.get()
    assert listing.street == "Klaterweg"
    assert listing.house_number == 9
    assert listing.house_letter == "R"
    assert listing.house_number_suffix == "A59"
    assert listing.postcode == "1271 KE"
    assert listing.city == "Huizen"


def test_submit_results_address_fields_default_to_null(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(listings=[listing_payload()])

    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        response = client.post(
            f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    listing = Listing.objects.get()
    assert listing.street is None
    assert listing.house_number is None
    assert listing.house_letter is None
    assert listing.house_number_suffix is None
    assert listing.postcode is None


def test_submit_results_does_not_redispatch_for_already_resolved_url(
    client, api_key_headers, scrape_payload, listing_payload
):
    """Re-scrape of the same URL shouldn't re-queue resolution — the listing
    is already linked to a residence; the bag_status guard preserves it."""
    existing_residence = cast(Residence, ResidenceFactory(bag_id="0003200000000900"))
    ListingFactory(
        residence=existing_residence,
        url="https://funda.nl/listing/already-resolved",
        bag_status=BagStatus.RESOLVED,
    )
    item = listing_payload(detail_url="https://funda.nl/listing/already-resolved")
    payload = scrape_payload(listings=[item])

    with mock.patch("scraping.api.resolve_bag.delay") as task_delay:
        response = client.post(
            f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    task_delay.assert_not_called()
    listing = Listing.objects.get(url="https://funda.nl/listing/already-resolved")
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence == existing_residence


def test_submit_results_re_scrape_updates_listing_per_portal_fields(
    client, api_key_headers, scrape_payload, listing_payload
):
    first = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://funda.nl/listing/re",
                price="€ 450.000 k.k.",
                status=ListingStatus.NEW.value,
            ),
        ],
    )
    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    listing_before = Listing.objects.get(url="https://funda.nl/listing/re")
    first_seen_at = listing_before.first_seen_at

    second = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://funda.nl/listing/re",
                price="€ 420.000 k.k.",
                status=ListingStatus.SALE_PENDING.value,
            ),
        ],
    )
    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    listing = Listing.objects.get(url="https://funda.nl/listing/re")
    assert listing.first_seen_at == first_seen_at  # never moves
    assert listing.price == "€ 420.000 k.k."
    assert listing.price_eur == 420_000
    assert listing.status == ListingStatus.SALE_PENDING
    assert listing.last_seen_at > first_seen_at


@pytest.mark.django_db(transaction=True)
@respx.mock
def test_submit_results_resolves_end_to_end(client, api_key_headers, scrape_payload, listing_payload):
    """End-to-end: POST → on_commit fires resolve_bag → BAG mocked → listing
    lands as RESOLVED with a Residence linked. `transaction=True` is needed
    so `transaction.on_commit` callbacks actually fire (the default
    non-transactional pytest-django marker swallows them)."""
    from scraping.bag_client import _BAG_BASE_URL

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        {
                            "openbareRuimteNaam": "Klaterweg",
                            "huisnummer": 9,
                            "huisletter": "R",
                            "huisnummertoevoeging": "A59",
                            "postcode": "1271KE",
                            "woonplaatsNaam": "Huizen",
                            "nummeraanduidingIdentificatie": "0402200000084467",
                        }
                    ]
                }
            },
        )
    )
    item = listing_payload(
        detail_url="https://funda.nl/listing/e2e",
        postcode="1271 KE",
        house_number=9,
        house_letter="R",
        house_number_suffix="A59",
        city="Huizen",
    )
    payload = scrape_payload(listings=[item])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    listing = Listing.objects.get(url="https://funda.nl/listing/e2e")
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence is not None
    assert listing.residence.bag_id == "0402200000084467"


def test_submit_results_rejects_inverted_timestamps(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[])
    payload["started_at"], payload["finished_at"] = (payload["finished_at"], payload["started_at"])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "image_url",
    [
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
        "https://example.com/" + ("x" * 2000),
    ],
    ids=["data_uri", "over_2000_chars"],
)
def test_submit_results_rejects_invalid_image_url(client, api_key_headers, scrape_payload, listing_payload, image_url):
    payload = scrape_payload(listings=[listing_payload(image_url=image_url)])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "image_url" in response.content.decode()
    assert Listing.objects.count() == 0


def test_submit_results_accepts_long_signed_image_url(client, api_key_headers, scrape_payload, listing_payload):
    # Real fastly/CDN URLs with signed query strings can exceed 500 chars
    # (observed up to ~700 on pararius); the 500-char cap was the original
    # source of the production 500. 1500 chars must round-trip end-to-end.
    long_url = "https://cdn.example.com/img/" + ("a" * 1500)
    payload = scrape_payload(listings=[listing_payload(image_url=long_url)])

    with _on_commit_inline(), mock.patch("scraping.api.resolve_bag.delay"):
        response = client.post(
            f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
        )

    assert response.status_code == 200
    assert Listing.objects.get().image_url == long_url


def test_submit_results_rejects_empty_title(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(listings=[listing_payload(title="")])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "title" in response.content.decode()
    assert Listing.objects.count() == 0


def test_submit_results_marks_run_failed_when_error_message(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[], error_message="boom")

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == ScrapeRunStatus.FAILED.value


def test_internal_endpoints_require_api_key(client, scrape_payload):
    last_run_url = f"/internal/v1/scrape-runs/{Website.FUNDA.value}/last-successful"
    results_url = f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results"
    payload = scrape_payload(listings=[])

    cases = [
        client.get(last_run_url),
        client.get(last_run_url, headers={"X-API-Key": "wrong"}),
        client.post(results_url, json=payload),
        client.post(results_url, json=payload, headers={"X-API-Key": "wrong"}),
    ]
    for response in cases:
        assert response.status_code == 401
