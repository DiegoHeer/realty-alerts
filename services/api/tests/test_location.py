from typing import cast

import httpx
import pytest
import respx

from scraping.models import BagStatus, Listing, ListingStatus, Residence
from scraping.resolvers.location import PdokLocationLookup
from tests.factories import ListingFactory, ResidenceFactory

_PDOK_BASE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1"
_PDOK_FREE_URL = f"{_PDOK_BASE_URL}/free"
_BAG_BASE_URL = "https://api.bag.kadaster.nl/lvbag/individuelebevragingen/v2"
_EP_ADRES_URL = "https://public.ep-online.nl/api/v5/PandEnergielabel/Adres"
_BODEMLOKET_URL = "https://gis.gdngeoservices.nl/standalone/rest/services/blk_gdn/lks_blk_rd_v1/MapServer/0/query"
_WFS_URL = "https://service.pdok.nl/rvo/indgebfunderingsproblematiek/wfs/v1_0"


def _mock_ep_online() -> None:
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=[]))


def _mock_bodemloket() -> None:
    respx.get(_BODEMLOKET_URL).mock(return_value=httpx.Response(200, json={"count": 0}))


_BESTEMMINGSPLAN_BASE_URL = "https://ruimte.omgevingswet.overheid.nl/ruimtelijke-plannen/api/opvragen/v4"


def _mock_bestemmingsplan() -> None:
    respx.post(url__startswith=_BESTEMMINGSPLAN_BASE_URL).mock(
        return_value=httpx.Response(200, json={"_embedded": {"plannen": []}}),
    )


def _mock_foundation_risk() -> None:
    respx.get(_WFS_URL).mock(return_value=httpx.Response(200, json={"type": "FeatureCollection", "features": []}))


def _pdok_response(
    lon: float = 4.89348311,
    lat: float = 52.37588008,
    buurtnaam: str = "Centrum",
    wijknaam: str = "Centrum",
) -> dict:
    return {
        "response": {"docs": [{"centroide_ll": f"POINT({lon} {lat})", "buurtnaam": buurtnaam, "wijknaam": wijknaam}]}
    }


def _pdok_empty_response() -> dict:
    return {"response": {"docs": []}}


# --- PdokLocationLookup unit tests ---


@respx.mock
def test_lookup_returns_location_result_on_success():
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json=_pdok_response(4.893, 52.376, "Jordaan", "Centrum"))
    )
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0363200000218780")
    assert result is not None
    assert result.latitude == pytest.approx(52.376)
    assert result.longitude == pytest.approx(4.893)
    assert result.neighbourhood == "Jordaan"
    assert result.district == "Centrum"


@respx.mock
def test_lookup_returns_none_on_empty_docs():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_empty_response()))
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0000000000000000")
    assert result is None


@respx.mock
def test_lookup_returns_none_on_http_error():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0363200000218780")
    assert result is None


@respx.mock
def test_lookup_returns_none_on_malformed_wkt():
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json={"response": {"docs": [{"centroide_ll": "GARBAGE"}]}})
    )
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0363200000218780")
    assert result is None


@respx.mock
def test_lookup_returns_none_on_missing_centroide_ll():
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json={"response": {"docs": [{}]}}))
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0363200000218780")
    assert result is None


@respx.mock
def test_lookup_sends_correct_query_params():
    route = respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_response()))
    with PdokLocationLookup() as lookup:
        lookup.lookup("0363200000218780")
    params = route.calls.last.request.url.params
    assert params["q"] == "nummeraanduiding_id:0363200000218780"
    assert params["fl"] == "centroide_ll,buurtnaam,wijknaam"
    assert params["rows"] == "1"


# --- resolve_bag integration tests ---


def _bag_address(**overrides) -> dict:
    base = {
        "openbareRuimteNaam": "Keizersgracht",
        "huisnummer": 1,
        "postcode": "1015AA",
        "woonplaatsNaam": "Amsterdam",
        "nummeraanduidingIdentificatie": "0363200000218780",
    }
    base.update(overrides)
    return base


def _pending_listing(**overrides) -> Listing:
    defaults: dict = {
        "residence": None,
        "bag_status": BagStatus.PENDING,
        "title": "Canal house",
        "price": "€ 750.000 k.k.",
        "price_eur": 750_000,
        "status": ListingStatus.NEW,
        "postcode": "1015AA",
        "house_number": 1,
        "city": "Amsterdam",
    }
    defaults.update(overrides)
    return cast(Listing, ListingFactory(**defaults))


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_enriches_coordinates_on_new_residence():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_response(4.893, 52.376)))
    _mock_ep_online()
    _mock_bodemloket()
    _mock_bestemmingsplan()
    _mock_foundation_risk()
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.residence is not None
    assert listing.residence.latitude == pytest.approx(52.376)
    assert listing.residence.longitude == pytest.approx(4.893)


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_skips_pdok_when_residence_fully_enriched():
    from scraping.tasks import resolve_bag

    existing = cast(
        Residence,
        ResidenceFactory(
            bag_id="0363200000218780", latitude=52.0, longitude=4.0, neighbourhood="Jordaan", district="Centrum"
        ),
    )
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    pdok_route = respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json=_pdok_response(4.893, 52.376)))
    _mock_bodemloket()
    _mock_bestemmingsplan()
    _mock_foundation_risk()
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    existing.refresh_from_db()
    assert existing.latitude == pytest.approx(52.0)
    assert existing.longitude == pytest.approx(4.0)
    assert existing.neighbourhood == "Jordaan"
    assert existing.district == "Centrum"
    assert not pdok_route.called


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_continues_when_pdok_coordinates_fail():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))
    _mock_ep_online()
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.bag_status == BagStatus.RESOLVED
    assert listing.residence is not None
    assert listing.residence.latitude is None
    assert listing.residence.longitude is None


# --- PdokLocationLookup neighbourhood-specific tests ---


@respx.mock
def test_lookup_returns_none_neighbourhood_when_fields_missing():
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json={"response": {"docs": [{"centroide_ll": "POINT(4.893 52.376)"}]}})
    )
    with PdokLocationLookup() as lookup:
        result = lookup.lookup("0363200000218780")
    assert result is not None
    assert result.latitude == pytest.approx(52.376)
    assert result.longitude == pytest.approx(4.893)
    assert result.neighbourhood is None
    assert result.district is None


# --- resolve_bag neighbourhood integration tests ---


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_enriches_neighbourhood_on_new_residence():
    from scraping.tasks import resolve_bag

    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json=_pdok_response(4.893, 52.376, "Jordaan", "Centrum"))
    )
    _mock_ep_online()
    _mock_bodemloket()
    _mock_bestemmingsplan()
    _mock_foundation_risk()
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    listing.refresh_from_db()
    assert listing.residence is not None
    assert listing.residence.neighbourhood == "Jordaan"
    assert listing.residence.district == "Centrum"


@pytest.mark.django_db
@respx.mock
def test_resolve_bag_enriches_neighbourhood_when_only_coordinates_exist():
    from scraping.tasks import resolve_bag

    existing = cast(
        Residence,
        ResidenceFactory(bag_id="0363200000218780", latitude=52.0, longitude=4.0),
    )
    respx.get(f"{_BAG_BASE_URL}/adressen").mock(
        return_value=httpx.Response(200, json={"_embedded": {"adressen": [_bag_address()]}})
    )
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json=_pdok_response(4.893, 52.376, "Jordaan", "Centrum"))
    )
    _mock_bodemloket()
    _mock_bestemmingsplan()
    _mock_foundation_risk()
    listing = _pending_listing()

    resolve_bag.delay(listing.pk).get(timeout=1)

    existing.refresh_from_db()
    assert existing.latitude == pytest.approx(52.0)
    assert existing.longitude == pytest.approx(4.0)
    assert existing.neighbourhood == "Jordaan"
    assert existing.district == "Centrum"
