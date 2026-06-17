from typing import cast

import httpx
import pytest
import respx

from scraping.models import Residence
from tests.factories import ResidenceFactory

_PDOK_FREE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"


def _pdok_response(lat: float = 52.376, lon: float = 4.893, buurt: str = "Jordaan", wijk: str = "Centrum") -> dict:
    return {"response": {"docs": [{"centroide_ll": f"POINT({lon} {lat})", "buurtnaam": buurt, "wijknaam": wijk}]}}


@pytest.mark.django_db
@respx.mock
def test_enrich_location_overwrites_existing_fields():
    from scraping.tasks import enrich_location

    residence = cast(
        Residence,
        ResidenceFactory(
            latitude=1.0,
            longitude=2.0,
            neighbourhood="Old",
            district="Old",
        ),
    )
    respx.get(_PDOK_FREE_URL).mock(
        return_value=httpx.Response(200, json=_pdok_response(52.376, 4.893, "Jordaan", "Centrum")),
    )

    enrich_location(residence.pk)

    residence.refresh_from_db()
    assert residence.latitude == 52.376
    assert residence.longitude == 4.893
    assert residence.neighbourhood == "Jordaan"
    assert residence.district == "Centrum"


@pytest.mark.django_db
@respx.mock
def test_enrich_location_no_op_when_pdok_returns_none():
    from scraping.tasks import enrich_location

    residence = cast(
        Residence,
        ResidenceFactory(latitude=1.0, longitude=2.0, neighbourhood="Old", district="Old"),
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(200, json={"response": {"docs": []}}))

    enrich_location(residence.pk)

    residence.refresh_from_db()
    assert residence.latitude == 1.0
    assert residence.longitude == 2.0
    assert residence.neighbourhood == "Old"
    assert residence.district == "Old"


@pytest.mark.django_db
@respx.mock
def test_enrich_location_no_op_on_http_error():
    from scraping.tasks import enrich_location

    residence = cast(
        Residence,
        ResidenceFactory(latitude=1.0, longitude=2.0),
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))

    enrich_location(residence.pk)

    residence.refresh_from_db()
    assert residence.latitude == 1.0
    assert residence.longitude == 2.0
