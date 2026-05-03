from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from scraping.models import (
    DeadListing,
    DeadListingReason,
    Listing,
    ListingUrl,
    ScrapeRun,
    ScrapeRunStatus,
    Website,
)

from tests.factories import ListingFactory, ListingUrlFactory, ScrapeRunFactory

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


@pytest.mark.parametrize("website", list(Website))
def test_submit_results_creates_run_and_listings(client, api_key_headers, scrape_payload, listing_payload, website):
    payload = scrape_payload(
        listings=[
            listing_payload(website=website.value),
            listing_payload(website=website.value),
        ]
    )

    response = client.post(f"/internal/v1/scrape-runs/{website.value}/results", json=payload, headers=api_key_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["website"] == website.value
    assert body["listings_found"] == 2
    assert body["new_properties_count"] == 2
    assert body["new_listing_urls_count"] == 2
    assert body["status"] == ScrapeRunStatus.SUCCESS.value
    assert ScrapeRun.objects.count() == 1
    assert Listing.objects.count() == 2
    assert ListingUrl.objects.count() == 2


def test_submit_results_dedups_existing_listings(client, api_key_headers, scrape_payload, listing_payload):
    existing = ListingFactory(bag_id="0003200000000001")
    ListingUrlFactory(listing=existing, url="https://example.com/listing/existing", website=Website.FUNDA)

    payload = scrape_payload(
        listings=[
            listing_payload(detail_url="https://example.com/listing/existing", bag_id="0003200000000001"),
            listing_payload(detail_url="https://example.com/listing/new", bag_id="0003200000000002"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["new_properties_count"] == 1
    assert body["new_listing_urls_count"] == 1
    assert Listing.objects.count() == 2
    assert ListingUrl.objects.count() == 2


def test_submit_results_dedups_within_payload_by_bag_id(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[
            listing_payload(detail_url="https://example.com/listing/1", bag_id="0003200000000001"),
            listing_payload(detail_url="https://example.com/listing/2", bag_id="0003200000000001"),
            listing_payload(detail_url="https://example.com/listing/3", bag_id="0003200000000002"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 3
    assert body["new_properties_count"] == 2
    assert Listing.objects.count() == 2


def test_submit_results_merges_cross_portal_listing(client, api_key_headers, scrape_payload, listing_payload):
    funda_payload = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://funda.nl/listing/abc",
                website=Website.FUNDA.value,
                bag_id="0003200000133985",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=funda_payload, headers=api_key_headers)

    pararius_payload = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://pararius.nl/listing/xyz",
                website=Website.PARARIUS.value,
                bag_id="0003200000133985",
            ),
        ],
    )
    response = client.post(
        f"/internal/v1/scrape-runs/{Website.PARARIUS.value}/results",
        json=pararius_payload,
        headers=api_key_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["new_properties_count"] == 0
    assert body["new_listing_urls_count"] == 1
    assert Listing.objects.count() == 1
    listing = Listing.objects.get()
    urls = list(listing.listing_urls.values_list("website", "url").order_by("website"))
    assert urls == [
        (Website.FUNDA.value, "https://funda.nl/listing/abc"),
        (Website.PARARIUS.value, "https://pararius.nl/listing/xyz"),
    ]


def test_submit_results_complements_missing_fields(client, api_key_headers, scrape_payload, listing_payload):
    first = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://example.com/listing/1",
                bag_id="0003200000000010",
                title="Original title",
                area_sqm=None,
                bedrooms=None,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)

    second = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://pararius.nl/listing/1",
                website=Website.PARARIUS.value,
                bag_id="0003200000000010",
                title="Different title from second portal",
                area_sqm=88.0,
                bedrooms=3,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.PARARIUS.value}/results", json=second, headers=api_key_headers)

    listing = Listing.objects.get(bag_id="0003200000000010")
    assert listing.title == "Original title"  # complement-only: existing wins
    assert listing.area_sqm == 88.0  # was None, filled by second scrape
    assert listing.bedrooms == 3  # was None, filled by second scrape


def test_submit_results_complement_does_not_overwrite_zero_bedrooms(
    client, api_key_headers, scrape_payload, listing_payload
):
    """A studio (bedrooms=0) is a real value, not a blank. The complement-only
    merge must not treat 0 as missing and overwrite it with a later scrape's
    non-zero count."""
    first = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://example.com/listing/studio",
                bag_id="0003200000000030",
                bedrooms=0,
                area_sqm=0.0,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)

    second = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://pararius.nl/listing/studio",
                website=Website.PARARIUS.value,
                bag_id="0003200000000030",
                bedrooms=3,
                area_sqm=88.0,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.PARARIUS.value}/results", json=second, headers=api_key_headers)

    listing = Listing.objects.get(bag_id="0003200000000030")
    assert listing.bedrooms == 0
    assert listing.area_sqm == 0.0


def test_submit_results_always_updates_price_and_scraped_at(client, api_key_headers, scrape_payload, listing_payload):
    first = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://example.com/listing/1",
                bag_id="0003200000000020",
                price="€ 450.000 k.k.",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    first_scraped_at = Listing.objects.get(bag_id="0003200000000020").scraped_at

    second = scrape_payload(
        listings=[
            listing_payload(
                detail_url="https://example.com/listing/1",
                bag_id="0003200000000020",
                price="€ 420.000 k.k.",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    listing = Listing.objects.get(bag_id="0003200000000020")
    assert listing.price == "€ 420.000 k.k."
    assert listing.price_eur == 420_000
    assert listing.scraped_at > first_scraped_at


def test_submit_results_rejects_inverted_timestamps(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[])
    payload["started_at"], payload["finished_at"] = (payload["finished_at"], payload["started_at"])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422


def test_submit_results_rejects_listing_without_bag_id(client, api_key_headers, scrape_payload, listing_payload):
    item = listing_payload()
    del item["bag_id"]
    payload = scrape_payload(listings=[item])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "bag_id" in response.content.decode()
    assert Listing.objects.count() == 0


@pytest.mark.parametrize(
    "image_url",
    [
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
        "https://example.com/" + ("x" * 2000),
    ],
    ids=["data_uri", "over_2000_chars"],
)
def test_submit_results_rejects_invalid_image_url(client, api_key_headers, scrape_payload, listing_payload, image_url):
    payload = scrape_payload(
        listings=[listing_payload(image_url=image_url)],
    )

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
    payload = scrape_payload(
        listings=[listing_payload(image_url=long_url)],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert Listing.objects.get().image_url == long_url


def test_submit_results_rejects_empty_title(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[listing_payload(title="")],
    )

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
    payload = scrape_payload(
        listings=[listing_payload()],
    )

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


def test_submit_results_persists_bag_id(client, api_key_headers, scrape_payload, listing_payload):
    payload = scrape_payload(
        listings=[listing_payload(bag_id="0003200000133985")],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert Listing.objects.get().bag_id == "0003200000133985"


def test_submit_results_persists_dead_listings(client, api_key_headers, scrape_payload, dead_listing_payload):
    payload = scrape_payload(
        listings=[],
        dead_listings=[
            dead_listing_payload(
                "https://example.com/dead/typo-postcode",
                reason=DeadListingReason.BAG_NO_MATCH.value,
                title="Probably typoed postcode",
                postcode="ZZZZ ZZ",
            ),
            dead_listing_payload(
                "https://example.com/dead/parse-failed",
                reason=DeadListingReason.PARSE_FAILED.value,
                title="No number to parse",
            ),
        ],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert DeadListing.objects.count() == 2
    by_reason = {d.reason: d for d in DeadListing.objects.all()}
    assert set(by_reason) == {DeadListingReason.BAG_NO_MATCH.value, DeadListingReason.PARSE_FAILED.value}
    assert by_reason[DeadListingReason.BAG_NO_MATCH.value].postcode == "ZZZZ ZZ"


def test_submit_results_dead_listings_re_categorise_on_repeat(
    client, api_key_headers, scrape_payload, dead_listing_payload
):
    """A dead listing that reappears in a later run with a different reason
    must update_or_create on detail_url instead of inserting a duplicate."""
    first = scrape_payload(
        dead_listings=[
            dead_listing_payload(
                "https://example.com/dead/repeat",
                reason=DeadListingReason.BAG_AMBIGUOUS.value,
            ),
        ],
    )
    second = scrape_payload(
        dead_listings=[
            dead_listing_payload(
                "https://example.com/dead/repeat",
                reason=DeadListingReason.BAG_NO_MATCH.value,
            ),
        ],
    )

    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    assert DeadListing.objects.count() == 1
    assert DeadListing.objects.get().reason == DeadListingReason.BAG_NO_MATCH.value


def test_submit_results_rejects_unknown_dead_listing_reason(
    client, api_key_headers, scrape_payload, dead_listing_payload
):
    payload = scrape_payload(
        dead_listings=[dead_listing_payload(reason="not_a_real_reason")],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert DeadListing.objects.count() == 0


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
