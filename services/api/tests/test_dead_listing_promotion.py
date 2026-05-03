from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from scraping.models import DeadListing, DeadListingReason, Listing, ListingUrl, Website
from scraping.services import DeadListingPromotionError, promote_dead_listing

from tests.factories import DeadListingFactory, ListingFactory, ListingUrlFactory

pytestmark = pytest.mark.django_db


def test_is_promotion_ready_true_when_all_required_fields_set():
    dead = DeadListingFactory.build(bag_id="0003200012345678", title="t", price="€ 1", city="Amsterdam")
    assert dead.is_promotion_ready is True
    assert dead.missing_promotion_fields == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("bag_id", None),
        ("bag_id", ""),
        ("title", ""),
        ("price", ""),
        ("city", ""),
    ],
)
def test_is_promotion_ready_false_when_required_field_missing(field, value):
    fields = {"bag_id": "0003200012345678", "title": "t", "price": "€ 1", "city": "Amsterdam"}
    fields[field] = value
    dead = DeadListingFactory.build(**fields)
    assert dead.is_promotion_ready is False
    assert field in dead.missing_promotion_fields


def test_promote_creates_listing_url_and_deletes_dead():
    dead = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000001",
            detail_url="https://example.com/dead/promote-1",
            title="Nice place",
            price="€ 350.000 k.k.",
            city="Amsterdam",
            street="Damrak",
            house_number=1,
            postcode="1012JS",
        ),
    )

    listing = promote_dead_listing(dead)

    assert isinstance(listing, Listing)
    assert listing.bag_id == "0003200000000001"
    assert listing.title == "Nice place"
    assert listing.price == "€ 350.000 k.k."
    assert listing.price_eur == 350_000
    assert listing.city == "Amsterdam"
    assert listing.street == "Damrak"
    assert listing.postcode == "1012JS"
    assert ListingUrl.objects.filter(url="https://example.com/dead/promote-1", listing=listing).exists()
    assert not DeadListing.objects.filter(pk=dead.pk).exists()


def test_promote_reuses_existing_listing_when_bag_id_matches():
    """Existing listing on Funda; same property comes via Pararius and lands in DLQ."""
    existing = cast(
        Listing,
        ListingFactory(
            bag_id="0003200000000002",
            title="Original title",
            price="€ 400.000 k.k.",
            price_eur=400_000,
            street="Original street",
            scraped_at=datetime.now(UTC),
        ),
    )
    ListingUrlFactory(listing=existing, website=Website.FUNDA, url="https://funda.example/orig")

    dead = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000002",
            website=Website.PARARIUS,
            detail_url="https://pararius.example/dead",
            title="Pararius title",
            price="€ 999.999 k.k.",
            city="Amsterdam",
            street="Different street",
            postcode="1011AB",
            scraped_at=datetime.now(UTC) - timedelta(days=2),
        ),
    )

    listing = promote_dead_listing(dead)

    assert listing.pk == existing.pk
    listing.refresh_from_db()
    # Older dead row must not regress price/scraped_at on a fresher listing.
    assert listing.price == "€ 400.000 k.k."
    assert listing.price_eur == 400_000
    assert listing.title == "Original title"
    assert listing.street == "Original street"
    # Complement-only: NULL fields are filled from dead row.
    assert listing.postcode == "1011AB"
    # Both URLs are now linked to the same listing.
    urls = set(ListingUrl.objects.filter(listing=listing).values_list("url", flat=True))
    assert urls == {"https://funda.example/orig", "https://pararius.example/dead"}
    assert not DeadListing.objects.filter(pk=dead.pk).exists()


def test_promote_overwrites_volatile_fields_when_dead_is_newer():
    existing = cast(
        Listing,
        ListingFactory(
            bag_id="0003200000000003",
            price="€ 100.000 k.k.",
            price_eur=100_000,
            scraped_at=datetime.now(UTC) - timedelta(days=5),
        ),
    )
    dead = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000003",
            detail_url="https://example.com/dead/newer",
            price="€ 250.000 k.k.",
            scraped_at=datetime.now(UTC),
        ),
    )

    promote_dead_listing(dead)

    existing.refresh_from_db()
    assert existing.price == "€ 250.000 k.k."
    assert existing.price_eur == 250_000


def test_promote_raises_when_not_ready():
    dead = cast(DeadListing, DeadListingFactory(bag_id=None))

    with pytest.raises(DeadListingPromotionError) as excinfo:
        promote_dead_listing(dead)

    assert "bag_id" in str(excinfo.value)
    assert DeadListing.objects.filter(pk=dead.pk).exists()
    assert Listing.objects.count() == 0


def test_promote_raises_when_url_attached_to_different_listing():
    other = cast(Listing, ListingFactory(bag_id="0003200000000004"))
    ListingUrlFactory(listing=other, url="https://example.com/dead/conflict")
    dead = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000005",  # different bag_id
            detail_url="https://example.com/dead/conflict",
        ),
    )

    with pytest.raises(DeadListingPromotionError) as excinfo:
        promote_dead_listing(dead)

    assert "different listing" in str(excinfo.value)
    assert DeadListing.objects.filter(pk=dead.pk).exists()


def test_promote_idempotent_when_url_already_attached_to_same_listing():
    """Re-promoting (or promoting after a manual ListingUrl insert) shouldn't error."""
    existing = cast(Listing, ListingFactory(bag_id="0003200000000006"))
    ListingUrlFactory(listing=existing, url="https://example.com/dead/already")
    dead = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000006",
            detail_url="https://example.com/dead/already",
        ),
    )

    listing = promote_dead_listing(dead)

    assert listing.pk == existing.pk
    assert ListingUrl.objects.filter(url="https://example.com/dead/already").count() == 1
    assert not DeadListing.objects.filter(pk=dead.pk).exists()


def test_upsert_dead_listings_skips_url_already_a_listing_url(
    client, api_key_headers, scrape_payload, dead_listing_payload
):
    """After a promotion, the next scrape run mustn't bounce the URL back into the DLQ."""
    listing = cast(Listing, ListingFactory(bag_id="0003200000000007"))
    ListingUrlFactory(listing=listing, url="https://example.com/dead/already-promoted")

    payload = scrape_payload(
        dead_listings=[
            dead_listing_payload(
                "https://example.com/dead/already-promoted",
                reason=DeadListingReason.BAG_NO_MATCH.value,
            ),
        ],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert DeadListing.objects.count() == 0


_DEAD_LISTING_CHANGELIST_URL = "/admin/scraping/deadlisting/"


def _run_promote_action(admin_client, dead_listing_pks: list[int]):
    return admin_client.post(
        _DEAD_LISTING_CHANGELIST_URL,
        data={
            "action": "promote_action",
            "_selected_action": [str(pk) for pk in dead_listing_pks],
            "index": "0",
        },
        follow=True,
    )


def test_promote_action_promotes_ready_skips_not_ready(admin_client):
    ready = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000010",
            detail_url="https://example.com/dead/ready",
            title="Ready row",
            price="€ 300.000 k.k.",
            city="Amsterdam",
        ),
    )
    not_ready = cast(
        DeadListing,
        DeadListingFactory(
            bag_id=None,
            detail_url="https://example.com/dead/not-ready",
        ),
    )

    response = _run_promote_action(admin_client, [ready.pk, not_ready.pk])

    assert response.status_code == 200
    assert not DeadListing.objects.filter(pk=ready.pk).exists()
    assert DeadListing.objects.filter(pk=not_ready.pk).exists()
    assert Listing.objects.filter(bag_id="0003200000000010").exists()
    summary = next(m for m in response.context["messages"] if "Promoted" in m.message)
    assert "Promoted 1" in summary.message
    assert "skipped 1" in summary.message
    assert "failed 0" in summary.message


def test_promote_action_continues_after_per_row_error(admin_client):
    """A URL conflict on one row must not block promotion of the others."""
    occupied = cast(Listing, ListingFactory(bag_id="0003200000000020"))
    ListingUrlFactory(listing=occupied, url="https://example.com/dead/conflicting-url")

    conflicting = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000021",  # different bag_id from occupied
            detail_url="https://example.com/dead/conflicting-url",
            title="Conflicting row",
            price="€ 200.000 k.k.",
            city="Amsterdam",
        ),
    )
    ok = cast(
        DeadListing,
        DeadListingFactory(
            bag_id="0003200000000022",
            detail_url="https://example.com/dead/ok",
            title="OK row",
            price="€ 250.000 k.k.",
            city="Amsterdam",
        ),
    )

    response = _run_promote_action(admin_client, [conflicting.pk, ok.pk])

    assert response.status_code == 200
    assert DeadListing.objects.filter(pk=conflicting.pk).exists()
    assert not DeadListing.objects.filter(pk=ok.pk).exists()
    assert Listing.objects.filter(bag_id="0003200000000022").exists()
    messages_text = [m.message for m in response.context["messages"]]
    assert any("Promoted 1" in m and "failed 1" in m for m in messages_text)
    assert any(f"DeadListing {conflicting.pk}" in m and "different listing" in m for m in messages_text)
