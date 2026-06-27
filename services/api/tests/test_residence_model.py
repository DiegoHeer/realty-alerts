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


def test_listing_attribute_columns_nullable():
    for name in ("bedroom_count", "bathroom_count", "surface_area_m2", "build_year"):
        assert Residence._meta.get_field(name).null is True


def test_listing_attribute_indexes_present():
    names = {idx.name for idx in Residence._meta.indexes}
    assert {
        "idx_res_bedroom_count",
        "idx_res_bathroom_count",
        "idx_res_surface_area",
        "idx_res_build_year",
    } <= names


def test_neighbourhood_code_column_nullable():
    field = Residence._meta.get_field("neighbourhood_code")
    assert field.null is True
    assert field.max_length == 12


def test_neighbourhood_code_index_present():
    names = {idx.name for idx in Residence._meta.indexes}
    assert "idx_res_neighbourhood_code" in names


@pytest.mark.django_db
def test_residence_stores_neighbourhood_code():
    residence = cast(Residence, ResidenceFactory(neighbourhood_code="BU03630000"))
    residence.refresh_from_db()
    assert residence.neighbourhood_code == "BU03630000"
