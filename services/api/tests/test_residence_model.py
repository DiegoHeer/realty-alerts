from typing import cast

import pytest

from scraping.models import DealType, Residence
from tests.factories import ResidenceFactory


def test_deal_type_defaults_to_sale():
    field = Residence._meta.get_field("deal_type")
    assert field.default == DealType.SALE


def test_expected_indexes_present():
    names = {idx.name for idx in Residence._meta.indexes}
    assert {
        "idx_res_dealtype_created",
        "idx_res_lat_lon",
        "idx_res_building_type",
        "idx_res_energy_label",
        "idx_residences_filters",
    } <= names


@pytest.mark.django_db
def test_deal_type_persists_default():
    residence = cast(Residence, ResidenceFactory())
    residence.refresh_from_db()
    assert residence.deal_type == DealType.SALE
