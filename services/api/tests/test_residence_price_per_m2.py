from typing import cast

import pytest

from scraping.models import Residence
from tests.factories import ResidenceFactory


@pytest.mark.django_db
class TestPricePerM2:
    def test_computed_from_price_and_area(self):
        residence = cast(Residence, ResidenceFactory(current_price_eur=500_000, surface_area_m2=100))
        residence.refresh_from_db()
        assert residence.price_per_m2 == pytest.approx(5000.0)

    def test_null_when_area_missing(self):
        residence = cast(Residence, ResidenceFactory(current_price_eur=500_000, surface_area_m2=None))
        residence.refresh_from_db()
        assert residence.price_per_m2 is None

    def test_null_when_area_zero(self):
        residence = cast(Residence, ResidenceFactory(current_price_eur=500_000, surface_area_m2=0))
        residence.refresh_from_db()
        assert residence.price_per_m2 is None

    def test_null_when_price_missing(self):
        residence = cast(Residence, ResidenceFactory(current_price_eur=None, surface_area_m2=100))
        residence.refresh_from_db()
        assert residence.price_per_m2 is None
