import pytest
from playwright.sync_api import sync_playwright
from pytest_mock import MockerFixture

from models import RealtyQuery
from scraper.vastgoed_nl import VastgoedNLScraper
from tests.scraper.conftest import mock_scrape_url_content


@pytest.fixture
def realty_query() -> RealtyQuery:
    return RealtyQuery(
        name="Vastgoed NL: houses and apartments",
        ntfy_topic="vastgoed-nl",
        cron_schedule="* * * * *",
        query_url="https://aanbod.vastgoednederland.nl/koopwoningen?q=den+haag",
        max_listing_page_number=999,
    )


@pytest.fixture
def scraper_detected_url() -> str:
    return "https://aanbod.vastgoednederland.nl/scraper-detected"


def test_scrape_last_page_number(mocker: MockerFixture, realty_query: RealtyQuery):
    mocker.patch.object(VastgoedNLScraper, "_connect_browser")
    mocker.patch.object(VastgoedNLScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        vastgoed_nl_scraper = VastgoedNLScraper(playwright, realty_query)
        last_page_number = vastgoed_nl_scraper._get_last_page()

    assert last_page_number == 67


def test_scrape_first_page(mocker: MockerFixture, realty_query: RealtyQuery):
    mocker.patch.object(VastgoedNLScraper, "_connect_browser")
    mocker.patch.object(VastgoedNLScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        vastgoed_nl_scraper = VastgoedNLScraper(playwright, realty_query)
        results = vastgoed_nl_scraper.get_page_results(page_number=1)

    assert len(results) == 8
    results.sort(key=lambda r: r.title)

    assert (
        results[0].detail_url
        == "https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576385-burgemeester-patijnlaan-712"
    )
    assert results[0].query_name == "Vastgoed NL: houses and apartments"
    assert results[0].title == "Burgemeester Patijnlaan 712"
    assert results[0].price == "€ 325.000,- k.k."
    assert results[0].image_url == "https://d1zsattj8yq64o.cloudfront.net/media/18883623/424x318_crop.jpg"
