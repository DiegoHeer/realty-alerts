from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from scraping.models import DeadResidence, DeadResidenceReason, Listing, Residence, Website
from scraping.services import DeadResidencePromotionError, promote_dead_residence

from tests.factories import DeadResidenceFactory, ListingFactory, ResidenceFactory

pytestmark = pytest.mark.django_db


def test_is_promotion_ready_true_when_all_required_fields_set():
    dead = DeadResidenceFactory.build(bag_id="0003200012345678", title="t", price="€ 1", city="Amsterdam")
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
    dead = DeadResidenceFactory.build(**fields)
    assert dead.is_promotion_ready is False
    assert field in dead.missing_promotion_fields


def test_promote_creates_listing_url_and_deletes_dead():
    dead = cast(
        DeadResidence,
        DeadResidenceFactory(
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

    residence = promote_dead_residence(dead)

    assert isinstance(residence, Residence)
    assert residence.bag_id == "0003200000000001"
    assert residence.title == "Nice place"
    assert residence.price == "€ 350.000 k.k."
    assert residence.price_eur == 350_000
    assert residence.city == "Amsterdam"
    assert residence.street == "Damrak"
    assert residence.postcode == "1012JS"
    assert Listing.objects.filter(url="https://example.com/dead/promote-1", residence=residence).exists()
    assert not DeadResidence.objects.filter(pk=dead.pk).exists()


def test_promote_reuses_existing_residence_when_bag_id_matches():
    """Existing residence on Funda; same property comes via Pararius and lands in DLQ."""
    existing = cast(
        Residence,
        ResidenceFactory(
            bag_id="0003200000000002",
            title="Original title",
            price="€ 400.000 k.k.",
            price_eur=400_000,
            street="Original street",
            scraped_at=datetime.now(UTC),
        ),
    )
    ListingFactory(residence=existing, website=Website.FUNDA, url="https://funda.example/orig")

    dead = cast(
        DeadResidence,
        DeadResidenceFactory(
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

    residence = promote_dead_residence(dead)

    assert residence.pk == existing.pk
    residence.refresh_from_db()
    # Older dead row must not regress price/scraped_at on a fresher residence.
    assert residence.price == "€ 400.000 k.k."
    assert residence.price_eur == 400_000
    assert residence.title == "Original title"
    assert residence.street == "Original street"
    # Complement-only: NULL fields are filled from dead row.
    assert residence.postcode == "1011AB"
    # Both URLs are now linked to the same residence.
    urls = set(Listing.objects.filter(residence=residence).values_list("url", flat=True))
    assert urls == {"https://funda.example/orig", "https://pararius.example/dead"}
    assert not DeadResidence.objects.filter(pk=dead.pk).exists()


def test_promote_overwrites_volatile_fields_when_dead_is_newer():
    existing = cast(
        Residence,
        ResidenceFactory(
            bag_id="0003200000000003",
            price="€ 100.000 k.k.",
            price_eur=100_000,
            scraped_at=datetime.now(UTC) - timedelta(days=5),
        ),
    )
    dead = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000003",
            detail_url="https://example.com/dead/newer",
            price="€ 250.000 k.k.",
            scraped_at=datetime.now(UTC),
        ),
    )

    promote_dead_residence(dead)

    existing.refresh_from_db()
    assert existing.price == "€ 250.000 k.k."
    assert existing.price_eur == 250_000


def test_promote_raises_when_not_ready():
    dead = cast(DeadResidence, DeadResidenceFactory(bag_id=None))

    with pytest.raises(DeadResidencePromotionError) as excinfo:
        promote_dead_residence(dead)

    assert "bag_id" in str(excinfo.value)
    assert DeadResidence.objects.filter(pk=dead.pk).exists()
    assert Residence.objects.count() == 0


def test_promote_raises_when_url_attached_to_different_residence():
    other = cast(Residence, ResidenceFactory(bag_id="0003200000000004"))
    ListingFactory(residence=other, url="https://example.com/dead/conflict")
    dead = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000005",  # different bag_id
            detail_url="https://example.com/dead/conflict",
        ),
    )

    with pytest.raises(DeadResidencePromotionError) as excinfo:
        promote_dead_residence(dead)

    assert "different residence" in str(excinfo.value)
    assert DeadResidence.objects.filter(pk=dead.pk).exists()


def test_promote_idempotent_when_url_already_attached_to_same_residence():
    """Re-promoting (or promoting after a manual Listing insert) shouldn't error."""
    existing = cast(Residence, ResidenceFactory(bag_id="0003200000000006"))
    ListingFactory(residence=existing, url="https://example.com/dead/already")
    dead = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000006",
            detail_url="https://example.com/dead/already",
        ),
    )

    residence = promote_dead_residence(dead)

    assert residence.pk == existing.pk
    assert Listing.objects.filter(url="https://example.com/dead/already").count() == 1
    assert not DeadResidence.objects.filter(pk=dead.pk).exists()


def test_upsert_dead_residences_skips_url_already_a_listing_url(
    client, api_key_headers, scrape_payload, dead_residence_payload
):
    """After a promotion, the next scrape run mustn't bounce the URL back into the DLQ."""
    residence = cast(Residence, ResidenceFactory(bag_id="0003200000000007"))
    ListingFactory(residence=residence, url="https://example.com/dead/already-promoted")

    payload = scrape_payload(
        dead_listings=[
            dead_residence_payload(
                "https://example.com/dead/already-promoted",
                reason=DeadResidenceReason.BAG_NO_MATCH.value,
            ),
        ],
    )

    response = client.post(
        f"/internal/v1/scrape-runs/{Website.FUNDA.value}/results", json=payload, headers=api_key_headers
    )

    assert response.status_code == 200
    assert DeadResidence.objects.count() == 0


_DEAD_RESIDENCE_CHANGELIST_URL = "/admin/scraping/deadresidence/"


def _run_promote_action(admin_client, dead_residence_pks: list[int]):
    return admin_client.post(
        _DEAD_RESIDENCE_CHANGELIST_URL,
        data={
            "action": "promote_action",
            "_selected_action": [str(pk) for pk in dead_residence_pks],
            "index": "0",
        },
        follow=True,
    )


def test_promote_action_promotes_ready_skips_not_ready(admin_client):
    ready = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000010",
            detail_url="https://example.com/dead/ready",
            title="Ready row",
            price="€ 300.000 k.k.",
            city="Amsterdam",
        ),
    )
    not_ready = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id=None,
            title="",
            detail_url="https://example.com/dead/not-ready",
        ),
    )

    response = _run_promote_action(admin_client, [ready.pk, not_ready.pk])

    assert response.status_code == 200
    assert not DeadResidence.objects.filter(pk=ready.pk).exists()
    assert DeadResidence.objects.filter(pk=not_ready.pk).exists()
    assert Residence.objects.filter(bag_id="0003200000000010").exists()

    messages_text = [m.message for m in response.context["messages"]]
    summary = next(m for m in messages_text if "Promoted" in m)
    assert "Promoted 1" in summary
    assert "skipped 1" in summary
    assert "failed 0" in summary
    not_ready_warning = next(m for m in messages_text if f"DeadResidence {not_ready.pk}" in m)
    assert "not ready" in not_ready_warning
    assert "bag_id" in not_ready_warning
    assert "title" in not_ready_warning


def test_promote_action_continues_after_per_row_error(admin_client):
    """A URL conflict on one row must not block promotion of the others."""
    occupied = cast(Residence, ResidenceFactory(bag_id="0003200000000020"))
    ListingFactory(residence=occupied, url="https://example.com/dead/conflicting-url")

    conflicting = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000021",  # different bag_id from occupied
            detail_url="https://example.com/dead/conflicting-url",
            title="Conflicting row",
            price="€ 200.000 k.k.",
            city="Amsterdam",
        ),
    )
    ok = cast(
        DeadResidence,
        DeadResidenceFactory(
            bag_id="0003200000000022",
            detail_url="https://example.com/dead/ok",
            title="OK row",
            price="€ 250.000 k.k.",
            city="Amsterdam",
        ),
    )

    response = _run_promote_action(admin_client, [conflicting.pk, ok.pk])

    assert response.status_code == 200
    assert DeadResidence.objects.filter(pk=conflicting.pk).exists()
    assert not DeadResidence.objects.filter(pk=ok.pk).exists()
    assert Residence.objects.filter(bag_id="0003200000000022").exists()
    messages_text = [m.message for m in response.context["messages"]]
    assert any("Promoted 1" in m and "failed 1" in m for m in messages_text)
    assert any(f"DeadResidence {conflicting.pk}" in m and "different residence" in m for m in messages_text)
