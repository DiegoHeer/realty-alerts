import pytest
from playwright.sync_api import sync_playwright
from pytest_mock import MockerFixture

from scraper.vastgoed_nl import VastgoedNLScraper
from tests.scraper.conftest import mock_scrape_url_content


@pytest.fixture
def query_url() -> str:
    return "https://aanbod.vastgoednederland.nl/koopwoningen?q=den+haag"


@pytest.fixture
def max_listing_page_number() -> int:
    return 999


@pytest.fixture
def scraper_detected_url() -> str:
    return "https://aanbod.vastgoednederland.nl/scraper-detected"


def test_scrape_last_page_number(mocker: MockerFixture, query_url, max_listing_page_number):
    mocker.patch.object(VastgoedNLScraper, "_connect_browser")
    mocker.patch.object(VastgoedNLScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        vastgoed_nl_scraper = VastgoedNLScraper(playwright, query_url, max_listing_page_number)
        last_page_number = vastgoed_nl_scraper._get_last_page()

    assert last_page_number == 67


def test_scrape_first_page(mocker: MockerFixture, query_url, max_listing_page_number):
    mocker.patch.object(VastgoedNLScraper, "_connect_browser")
    mocker.patch.object(VastgoedNLScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        vastgoed_nl_scraper = VastgoedNLScraper(playwright, query_url, max_listing_page_number)
        results = vastgoed_nl_scraper.get_page_results(page_number=1)

    assert len(results) == 8
    results.sort(key=lambda r: r.title)

    assert (
        results[0].detail_url
        == "https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576385-burgemeester-patijnlaan-712"
    )
    assert results[0].title == "Burgemeester Patijnlaan 712"
    assert results[0].price == "€ 325.000,- k.k."
    assert results[0].image_url == "https://d1zsattj8yq64o.cloudfront.net/media/18883623/424x318_crop.jpg"
