from datetime import date
from typing import cast

import httpx
import pytest
import respx

from scraping.models import BuildingType, EnergyLabel, Residence
from tests.factories import ResidenceFactory

_PDOK_FREE_URL = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
_EP_ADRES_URL = "https://public.ep-online.nl/api/v5/PandEnergielabel/Adres"


def _ep_response(
    building_type: str = "Appartement",
    energy_label: str = "B",
    valid_until: str = "2035-01-15",
) -> list[dict]:
    return [{"Gebouwtype": building_type, "Energieklasse": energy_label, "Geldig_tot": valid_until}]


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
        ResidenceFactory(latitude=1.0, longitude=2.0, neighbourhood="Old", district="Old"),
    )
    respx.get(_PDOK_FREE_URL).mock(return_value=httpx.Response(503))

    enrich_location(residence.pk)

    residence.refresh_from_db()
    assert residence.latitude == 1.0
    assert residence.longitude == 2.0
    assert residence.neighbourhood == "Old"
    assert residence.district == "Old"


@pytest.mark.django_db
@respx.mock
def test_enrich_building_details_overwrites_existing_fields(settings):
    from scraping.tasks import enrich_building_details

    settings.EP_ONLINE_API_KEY = "test-key"
    residence = cast(
        Residence,
        ResidenceFactory(
            postcode="1015AA",
            house_number=1,
            building_type=BuildingType.DETACHED,
            energy_label=EnergyLabel.G,
            energy_label_valid_until=date(2020, 1, 1),
        ),
    )
    respx.get(_EP_ADRES_URL).mock(
        return_value=httpx.Response(200, json=_ep_response("Appartement", "B", "2034-06-01")),
    )

    enrich_building_details(residence.pk)

    residence.refresh_from_db()
    assert residence.building_type == BuildingType.APARTMENT
    assert residence.energy_label == EnergyLabel.B
    assert residence.energy_label_valid_until == date(2034, 6, 1)


@pytest.mark.django_db
@respx.mock
def test_enrich_building_details_no_op_when_api_returns_none(settings):
    from scraping.tasks import enrich_building_details

    settings.EP_ONLINE_API_KEY = "test-key"
    residence = cast(
        Residence,
        ResidenceFactory(
            postcode="1015AA",
            house_number=1,
            building_type=BuildingType.DETACHED,
        ),
    )
    respx.get(_EP_ADRES_URL).mock(return_value=httpx.Response(200, json=[]))

    enrich_building_details(residence.pk)

    residence.refresh_from_db()
    assert residence.building_type == BuildingType.DETACHED


@pytest.mark.django_db
def test_enrich_building_details_skips_when_no_postcode(settings):
    from scraping.tasks import enrich_building_details

    settings.EP_ONLINE_API_KEY = "test-key"
    residence = cast(Residence, ResidenceFactory(postcode=None, house_number=None))

    enrich_building_details(residence.pk)

    residence.refresh_from_db()
    assert residence.building_type is None


_BODEMLOKET_URL = "https://www.gdngeoservices.nl/arcgis/rest/services/blk/lks_blk_rd/MapServer/1/query"


@pytest.mark.django_db
@respx.mock
def test_enrich_soil_status_stores_count():
    from scraping.tasks import enrich_soil_status

    residence = cast(Residence, ResidenceFactory(latitude=52.376, longitude=4.893, soil_wbb_count=None))
    respx.get(_BODEMLOKET_URL).mock(return_value=httpx.Response(200, json={"count": 3}))

    enrich_soil_status(residence.pk)

    residence.refresh_from_db()
    assert residence.soil_wbb_count == 3
    assert residence.soil_fetched_at is not None


@pytest.mark.django_db
@respx.mock
def test_enrich_soil_status_stores_zero():
    from scraping.tasks import enrich_soil_status

    residence = cast(Residence, ResidenceFactory(latitude=52.376, longitude=4.893))
    respx.get(_BODEMLOKET_URL).mock(return_value=httpx.Response(200, json={"count": 0}))

    enrich_soil_status(residence.pk)

    residence.refresh_from_db()
    assert residence.soil_wbb_count == 0
    assert residence.soil_fetched_at is not None


@pytest.mark.django_db
@respx.mock
def test_enrich_soil_status_no_op_when_no_coordinates():
    from scraping.tasks import enrich_soil_status

    residence = cast(Residence, ResidenceFactory(latitude=None, longitude=None))

    enrich_soil_status(residence.pk)

    residence.refresh_from_db()
    assert residence.soil_wbb_count is None
