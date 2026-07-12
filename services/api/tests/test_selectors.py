import pytest

from scraping.selectors import residence_summary_qs
from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
def test_residence_summary_qs_annotates_cover_image():
    residence = ResidenceFactory()
    ListingFactory(residence=residence, image_url="https://example.com/cover.jpg")
    obj = residence_summary_qs().get(id=residence.id)
    assert obj.cover_image_url == "https://example.com/cover.jpg"
