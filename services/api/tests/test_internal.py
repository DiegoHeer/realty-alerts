from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from scraping.models import (
    DeadResidence,
    DeadResidenceReason,
    ListingStatus,
    ListingUrl,
    Residence,
    ScrapeRun,
    ScrapeRunStatus,
    Website,
)

from tests.factories import ListingUrlFactory, ResidenceFactory, ScrapeRunFactory

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
def test_submit_results_creates_run_and_residences(client, api_key_headers, scrape_payload, residence_payload, website):
    payload = scrape_payload(
        listings=[
            residence_payload(website=website.value),
            residence_payload(website=website.value),
        ]
    )

    response = client.post(f"/internal/v1/scrape-runs/{website.value}/results", json=payload, headers=api_key_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["website"] == website.value
    assert body["listings_found"] == 2
    assert body["new_residences_count"] == 2
    assert body["new_listing_urls_count"] == 2
    assert body["status"] == ScrapeRunStatus.SUCCESS.value
    assert ScrapeRun.objects.count() == 1
    assert Residence.objects.count() == 2
    assert ListingUrl.objects.count() == 2


def test_submit_results_dedups_existing_residences(client, api_key_headers, scrape_payload, residence_payload):
    existing = ResidenceFactory(bag_id="0003200000000001")
    ListingUrlFactory(listing=existing, url="https://example.com/listing/existing", website=Website.FUNDA)

    payload = scrape_payload(
        listings=[
            residence_payload(detail_url="https://example.com/listing/existing", bag_id="0003200000000001"),
            residence_payload(detail_url="https://example.com/listing/new", bag_id="0003200000000002"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 2
    assert body["new_residences_count"] == 1
    assert body["new_listing_urls_count"] == 1
    assert Residence.objects.count() == 2
    assert ListingUrl.objects.count() == 2


def test_submit_results_dedups_within_payload_by_bag_id(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[
            residence_payload(detail_url="https://example.com/listing/1", bag_id="0003200000000001"),
            residence_payload(detail_url="https://example.com/listing/2", bag_id="0003200000000001"),
            residence_payload(detail_url="https://example.com/listing/3", bag_id="0003200000000002"),
        ]
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["listings_found"] == 3
    assert body["new_residences_count"] == 2
    assert Residence.objects.count() == 2


def test_submit_results_merges_cross_portal_residence(client, api_key_headers, scrape_payload, residence_payload):
    funda_payload = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://funda.nl/listing/abc",
                website=Website.FUNDA.value,
                bag_id="0003200000133985",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=funda_payload, headers=api_key_headers)

    pararius_payload = scrape_payload(
        listings=[
            residence_payload(
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
    assert body["new_residences_count"] == 0
    assert body["new_listing_urls_count"] == 1
    assert Residence.objects.count() == 1
    residence = Residence.objects.get()
    urls = list(residence.listing_urls.values_list("website", "url").order_by("website"))
    assert urls == [
        (Website.FUNDA.value, "https://funda.nl/listing/abc"),
        (Website.PARARIUS.value, "https://pararius.nl/listing/xyz"),
    ]


def test_submit_results_complements_missing_fields(client, api_key_headers, scrape_payload, residence_payload):
    first = scrape_payload(
        listings=[
            residence_payload(
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
            residence_payload(
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

    residence = Residence.objects.get(bag_id="0003200000000010")
    assert residence.title == "Original title"  # complement-only: existing wins
    assert residence.area_sqm == 88.0  # was None, filled by second scrape
    assert residence.bedrooms == 3  # was None, filled by second scrape


def test_submit_results_complement_does_not_overwrite_zero_bedrooms(
    client, api_key_headers, scrape_payload, residence_payload
):
    """A studio (bedrooms=0) is a real value, not a blank. The complement-only
    merge must not treat 0 as missing and overwrite it with a later scrape's
    non-zero count."""
    first = scrape_payload(
        listings=[
            residence_payload(
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
            residence_payload(
                detail_url="https://pararius.nl/listing/studio",
                website=Website.PARARIUS.value,
                bag_id="0003200000000030",
                bedrooms=3,
                area_sqm=88.0,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.PARARIUS.value}/results", json=second, headers=api_key_headers)

    residence = Residence.objects.get(bag_id="0003200000000030")
    assert residence.bedrooms == 0
    assert residence.area_sqm == 0.0


def test_submit_results_always_updates_price_and_scraped_at(client, api_key_headers, scrape_payload, residence_payload):
    first = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://example.com/listing/1",
                bag_id="0003200000000020",
                price="€ 450.000 k.k.",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    first_scraped_at = Residence.objects.get(bag_id="0003200000000020").scraped_at

    second = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://example.com/listing/1",
                bag_id="0003200000000020",
                price="€ 420.000 k.k.",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    residence = Residence.objects.get(bag_id="0003200000000020")
    assert residence.price == "€ 420.000 k.k."
    assert residence.price_eur == 420_000
    assert residence.scraped_at > first_scraped_at


def test_submit_results_persists_status_and_updates_on_repeat(
    client, api_key_headers, scrape_payload, residence_payload
):
    first = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://example.com/listing/status",
                bag_id="0003200000000099",
                status=ListingStatus.SALE_PENDING.value,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    assert Residence.objects.get(bag_id="0003200000000099").status == ListingStatus.SALE_PENDING

    second = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://example.com/listing/status",
                bag_id="0003200000000099",
                status=ListingStatus.SOLD.value,
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)
    assert Residence.objects.get(bag_id="0003200000000099").status == ListingStatus.SOLD


def test_submit_results_sets_status_changed_at_on_create(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[
            residence_payload(
                detail_url="https://example.com/listing/anchor",
                bag_id="0003200000000201",
                status=ListingStatus.SOLD.value,
            ),
        ],
    )
    before = datetime.now(UTC)

    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers)

    residence = Residence.objects.get(bag_id="0003200000000201")
    assert residence.status_changed_at is not None
    assert residence.status_changed_at >= before


def test_submit_results_does_not_bump_status_changed_at_when_status_unchanged(
    client, api_key_headers, scrape_payload, residence_payload
):
    detail_url = "https://example.com/listing/no-bump"
    bag_id = "0003200000000202"
    first = scrape_payload(
        listings=[
            residence_payload(detail_url=detail_url, bag_id=bag_id, status=ListingStatus.NEW.value),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    initial_anchor = Residence.objects.get(bag_id=bag_id).status_changed_at

    second = scrape_payload(
        listings=[
            residence_payload(
                detail_url=detail_url,
                bag_id=bag_id,
                status=ListingStatus.NEW.value,
                price="€ 410.000 k.k.",
            ),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    assert Residence.objects.get(bag_id=bag_id).status_changed_at == initial_anchor


def test_submit_results_bumps_status_changed_at_on_transition(
    client, api_key_headers, scrape_payload, residence_payload
):
    detail_url = "https://example.com/listing/transition"
    bag_id = "0003200000000203"
    first = scrape_payload(
        listings=[
            residence_payload(detail_url=detail_url, bag_id=bag_id, status=ListingStatus.NEW.value),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    initial_anchor = Residence.objects.get(bag_id=bag_id).status_changed_at

    second = scrape_payload(
        listings=[
            residence_payload(detail_url=detail_url, bag_id=bag_id, status=ListingStatus.SOLD.value),
        ],
    )
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    updated = Residence.objects.get(bag_id=bag_id)
    assert updated.status == ListingStatus.SOLD
    assert updated.status_changed_at > initial_anchor


def test_submit_results_rejects_inverted_timestamps(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[])
    payload["started_at"], payload["finished_at"] = (payload["finished_at"], payload["started_at"])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422


def test_submit_results_rejects_residence_without_bag_id(client, api_key_headers, scrape_payload, residence_payload):
    item = residence_payload()
    del item["bag_id"]
    payload = scrape_payload(listings=[item])

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "bag_id" in response.content.decode()
    assert Residence.objects.count() == 0


@pytest.mark.parametrize(
    "image_url",
    [
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg'/>",
        "https://example.com/" + ("x" * 2000),
    ],
    ids=["data_uri", "over_2000_chars"],
)
def test_submit_results_rejects_invalid_image_url(
    client, api_key_headers, scrape_payload, residence_payload, image_url
):
    payload = scrape_payload(
        listings=[residence_payload(image_url=image_url)],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "image_url" in response.content.decode()
    assert Residence.objects.count() == 0


def test_submit_results_accepts_long_signed_image_url(client, api_key_headers, scrape_payload, residence_payload):
    # Real fastly/CDN URLs with signed query strings can exceed 500 chars
    # (observed up to ~700 on pararius); the 500-char cap was the original
    # source of the production 500. 1500 chars must round-trip end-to-end.
    long_url = "https://cdn.example.com/img/" + ("a" * 1500)
    payload = scrape_payload(
        listings=[residence_payload(image_url=long_url)],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert Residence.objects.get().image_url == long_url


def test_submit_results_rejects_empty_title(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[residence_payload(title="")],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert "title" in response.content.decode()
    assert Residence.objects.count() == 0


def test_submit_results_marks_run_failed_when_error_message(client, api_key_headers, scrape_payload):
    payload = scrape_payload(listings=[], error_message="boom")

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == ScrapeRunStatus.FAILED.value


def test_submit_results_persists_structured_address_fields(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[
            residence_payload(
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
    residence = Residence.objects.get()
    assert residence.street == "Klaterweg"
    assert residence.house_number == 9
    assert residence.house_letter == "R"
    assert residence.house_number_suffix == "A59"
    assert residence.postcode == "1271 KE"
    assert residence.city == "Huizen"


def test_submit_results_address_fields_default_to_null(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[residence_payload()],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    residence = Residence.objects.get()
    assert residence.street is None
    assert residence.house_number is None
    assert residence.house_letter is None
    assert residence.house_number_suffix is None
    assert residence.postcode is None


def test_submit_results_persists_bag_id(client, api_key_headers, scrape_payload, residence_payload):
    payload = scrape_payload(
        listings=[residence_payload(bag_id="0003200000133985")],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert Residence.objects.get().bag_id == "0003200000133985"


def test_submit_results_persists_dead_residences(client, api_key_headers, scrape_payload, dead_residence_payload):
    payload = scrape_payload(
        listings=[],
        dead_listings=[
            dead_residence_payload(
                "https://example.com/dead/typo-postcode",
                reason=DeadResidenceReason.BAG_NO_MATCH.value,
                title="Probably typoed postcode",
                postcode="ZZZZ ZZ",
            ),
            dead_residence_payload(
                "https://example.com/dead/parse-failed",
                reason=DeadResidenceReason.PARSE_FAILED.value,
                title="No number to parse",
            ),
        ],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert DeadResidence.objects.count() == 2
    by_reason = {d.reason: d for d in DeadResidence.objects.all()}
    assert set(by_reason) == {DeadResidenceReason.BAG_NO_MATCH.value, DeadResidenceReason.PARSE_FAILED.value}
    assert by_reason[DeadResidenceReason.BAG_NO_MATCH.value].postcode == "ZZZZ ZZ"


def test_submit_results_dead_residences_re_categorise_on_repeat(
    client, api_key_headers, scrape_payload, dead_residence_payload
):
    """A dead residence that reappears in a later run with a different reason
    must update_or_create on detail_url instead of inserting a duplicate."""
    first = scrape_payload(
        dead_listings=[
            dead_residence_payload(
                "https://example.com/dead/repeat",
                reason=DeadResidenceReason.BAG_AMBIGUOUS.value,
            ),
        ],
    )
    second = scrape_payload(
        dead_listings=[
            dead_residence_payload(
                "https://example.com/dead/repeat",
                reason=DeadResidenceReason.BAG_NO_MATCH.value,
            ),
        ],
    )

    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=first, headers=api_key_headers)
    client.post(f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=second, headers=api_key_headers)

    assert DeadResidence.objects.count() == 1
    assert DeadResidence.objects.get().reason == DeadResidenceReason.BAG_NO_MATCH.value


def test_submit_results_rejects_unknown_dead_residence_reason(
    client, api_key_headers, scrape_payload, dead_residence_payload
):
    payload = scrape_payload(
        dead_listings=[dead_residence_payload(reason="not_a_real_reason")],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 422
    assert DeadResidence.objects.count() == 0


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
