from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from pytest_mock import MockerFixture

from scraper.base import ScrapingException
from scraper.funda import FundaScraper
from tests.scraper.conftest import mock_scrape_url_content

MOCK_DATA_DIR = Path(__file__).resolve().parent / "data"


@pytest.fixture
def query_url() -> str:
    return "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D"


@pytest.fixture
def max_listing_page_number() -> int:
    return 999


@pytest.fixture
def detail_url() -> str:
    return "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"


@pytest.fixture
def scraper_detected_url() -> str:
    return "https://www.funda.nl/scraper-detected"


def test_scrape_last_page_number(mocker: MockerFixture, query_url, max_listing_page_number):
    mocker.patch.object(FundaScraper, "_connect_browser")
    mocker.patch.object(FundaScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, query_url, max_listing_page_number)
        last_page_number = funda_scraper._get_last_page()

    assert last_page_number == 666


def test_scrape_detail_urls_of_query_page(mocker: MockerFixture, query_url, max_listing_page_number):
    mocker.patch.object(FundaScraper, "_connect_browser")
    mocker.patch.object(FundaScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, query_url, max_listing_page_number)
        detail_urls = funda_scraper._scrape_urls_per_page_number(page_number=1)

    assert len(detail_urls) == 30


def test_scrape_detail_page(mocker: MockerFixture, query_url, max_listing_page_number, detail_url: str):
    mocker.patch.object(FundaScraper, "_connect_browser")
    mocker.patch.object(FundaScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, query_url, max_listing_page_number)
        query_result = funda_scraper.scrape_detail_page(detail_url)

    assert query_result.detail_url == "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"
    assert query_result.title == "Bangert 58"
    assert query_result.price == "€ 775.000 k.k."
    assert query_result.image_url == "https://cloud.funda.nl/valentina_media/212/433/008_720x480.jpg"


def test_scrape_detected(mocker: MockerFixture, query_url, max_listing_page_number, scraper_detected_url: str):
    mocker.patch.object(FundaScraper, "_connect_browser")
    mocker.patch.object(FundaScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with pytest.raises(ScrapingException) as exc:
        with sync_playwright() as playwright:
            funda_scraper = FundaScraper(playwright, query_url, max_listing_page_number)
            funda_scraper.scrape_detail_page(scraper_detected_url)

    assert exc.value.args[0] == "Scraping was detected when trying to access url: https://www.funda.nl/scraper-detected"
