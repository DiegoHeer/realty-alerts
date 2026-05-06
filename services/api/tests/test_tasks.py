from typing import cast

import httpx
import pytest
import respx

from scraping.bag_client import _BAG_BASE_URL
from scraping.models import BagStatus, Listing, ListingStatus, Residence
from tests.factories import ListingFactory, ResidenceFactory


def test_ping_returns_pong_under_eager_mode():
    from scraping.tasks import ping

    result = ping.delay()
    assert result.get(timeout=1) == "pong"


@respx.mock
def test_dispatch_scrape_posts_payload_and_returns_run_id(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    route = respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))

    run_id = dispatch_scrape.delay("funda", "run-abc").get(timeout=1)

    assert run_id == "run-abc"
    assert route.called
    body = route.calls.last.request.content.decode()
    assert '"website":"funda"' in body
    assert '"run_id":"run-abc"' in body


@respx.mock
def test_dispatch_scrape_generates_run_id_when_missing(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"
    respx.post("http://webhook.test/scrape").mock(return_value=httpx.Response(200))

    run_id = dispatch_scrape.delay("pararius").get(timeout=1)

    assert run_id and len(run_id) == 32  # uuid4 hex


def test_dispatch_scrape_short_circuits_when_url_unset(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = None

    # No respx mock — if the task attempted an HTTP call it would fail.
    run_id = dispatch_scrape.delay("funda", "run-skip").get(timeout=1)

    assert run_id == "run-skip"


def test_dispatch_scrape_rejects_unknown_website(settings):
    from scraping.tasks import dispatch_scrape

    settings.ARGO_EVENTS_WEBHOOK_URL = "http://webhook.test/scrape"

    with pytest.raises(ValueError):
        dispatch_scrape.delay("not-a-real-site").get(timeout=1)


def _bag_address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Klaterweg",
        "huisnummer": 9,
        "huisletter": "R",
        "huisnummertoevoeging": "A59",
        "postcode": "1271KE",
        "woonplaatsNaam": "Huizen",
        "nummeraanduidingIdentificatie": "0402200000084467",
    }
    base.update(overrides)
    return base


def _pending_listing(**overrides) -> Listing:
    defaults: dict = {
        "residence": None,
        "bag_status": BagStatus.PENDING,
        "title": "Sunny duplex",
        "price": "€ 425.000 k.k.",
        "price_eur": 425_000,
        "image_url": "https://cdn.example.com/abc.jpg",
        "status": ListingStatus.NEW,
        "postcode": "1271 KE",
        "house_number": 9,
        "house_letter": "R",
        "house_number_suffix": "A59",
        "city": "Huizen",
    }
    defaults.update(overrides)
    return cast(Listing, ListingFactory(**defaults))


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_links_listing_to_residence_and_reconciles():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.bag_resolved_at is not None
    assert listing.residence is not None
    assert listing.residence.bag_id == "0402200000084467"
    assert listing.residence.street == "Klaterweg"
    assert listing.residence.city == "Huizen"
    assert listing.residence.current_price_eur == 425_000
    assert listing.residence.current_status == ListingStatus.NEW


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_attaches_to_existing_residence_for_cross_portal():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    existing = cast(Residence, ResidenceFactory(bag_id="0402200000084467", price_eur=520_000))
    listing = _pending_listing(price_eur=480_000)

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.residence == existing
    existing.refresh_from_db()
    assert existing.current_price_eur == 480_000  # min across resolved listings


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_marks_no_match_when_bag_returns_empty():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(return_value=httpx.Response(200, json={"_embedded": {"adressen": []}}))
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.BAG_NO_MATCH
    assert listing.residence is None
    assert listing.bag_failure_reason is not None
    assert "no_match" in listing.bag_failure_reason


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_marks_ambiguous_when_bag_returns_multiple():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(
            200,
            json={
                "_embedded": {
                    "adressen": [
                        _bag_address(nummeraanduidingIdentificatie="0402200000000001"),
                        _bag_address(nummeraanduidingIdentificatie="0402200000000002"),
                    ]
                }
            },
        )
    )
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.BAG_AMBIGUOUS
    assert listing.residence is None


@pytest.mark.django_db
def test_resolve_bag_marks_missing_address_when_postcode_blank():
    from scraping.tasks import resolve_bag

    listing = _pending_listing(postcode=None)

    # No respx mock — task must short-circuit before any HTTP call.
    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.MISSING_ADDRESS
    assert listing.residence is None


@pytest.mark.django_db
def test_resolve_bag_is_idempotent_on_already_resolved_listing():
    from scraping.tasks import resolve_bag

    residence = cast(Residence, ResidenceFactory())
    listing = cast(
        Listing,
        ListingFactory(
            residence=residence,
            bag_status=BagStatus.RESOLVED,
            postcode="1271 KE",
            house_number=9,
        ),
    )

    # No respx mock — already-resolved listings must not hit BAG.
    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence == residence


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_propagates_5xx_so_celery_retries():
    """Bypass the @shared_task wrapper to check the underlying function raises
    HTTPStatusError on 5xx. The decorator's `autoretry_for=(httpx.HTTPError,)`
    + `retry_backoff=True` (covered by the task definition itself, not this
    test) handles the retry — we just need to be sure we don't swallow the
    error and leave the listing terminally stuck."""
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(return_value=httpx.Response(503))
    listing = _pending_listing()

    with pytest.raises(httpx.HTTPStatusError):
        resolve_bag(listing.pk)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.PENDING
