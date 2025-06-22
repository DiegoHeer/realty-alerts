from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright
from pytest_mock import MockerFixture

from models import RealtyQuery
from scraper.base import ScrapingException
from scraper.funda import FundaScraper

MOCK_DATA_DIR = Path(__file__).resolve().parent / "data"


def mock_get_url_content(url: str) -> str:
    url_to_file_name = {
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D": "page_listing",
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=1": "page_1",
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=2": "page_2",
        "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/": "page_detail",
        "https://www.funda.nl/scraper-detected": "scraper_detected",
    }

    try:
        return _load_html_file(file_name=f"{url_to_file_name[url]}.html")
    except KeyError:
        raise KeyError(f"No mock defined for URL: {url}")


def _load_html_file(file_name: str) -> str:
    file_path = MOCK_DATA_DIR / file_name
    return file_path.read_text(encoding="utf-8")


@pytest.fixture
def realty_query() -> RealtyQuery:
    return RealtyQuery(
        name="Funda: houses and apartments",
        cron_schedule="* * * * *",
        query_url="https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D",
        max_listing_page_number=2,
    )


@pytest.fixture
def detail_url() -> str:
    return "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"


@pytest.fixture
def scraper_detected_url() -> str:
    return "https://www.funda.nl/scraper-detected"


def test_scrape_detail_urls_of_query_page(mocker: MockerFixture, realty_query: RealtyQuery):
    mocker.patch.object(FundaScraper, "_get_url_content", side_effect=mock_get_url_content)

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, realty_query)
        detail_urls = funda_scraper.scrape_detail_urls_of_listing_page()

    assert len(detail_urls) > 0


def test_scrape_detail_page(mocker: MockerFixture, realty_query: RealtyQuery, detail_url: str):
    mocker.patch.object(FundaScraper, "_get_url_content", side_effect=mock_get_url_content)

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, realty_query)
        query_result = funda_scraper.scrape_detail_page(detail_url)

    assert query_result.detail_url == "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"
    assert query_result.title == "Bangert 58"
    assert query_result.price == "€ 775.000 k.k."
    assert query_result.image_url == "https://cloud.funda.nl/valentina_media/212/433/008_720x480.jpg"


def test_scrape_detected(mocker: MockerFixture, realty_query: RealtyQuery, scraper_detected_url: str):
    mocker.patch.object(FundaScraper, "_get_url_content", side_effect=mock_get_url_content)

    with pytest.raises(ScrapingException) as exc:
        with sync_playwright() as playwright:
            funda_scraper = FundaScraper(playwright, realty_query)
            funda_scraper.scrape_detail_page(scraper_detected_url)

    assert exc.value.args[0] == "Scraping was detected when trying to access url: https://www.funda.nl/scraper-detected"
