import pytest
from playwright.sync_api import sync_playwright
from pytest_mock import MockerFixture

from models import RealtyQuery
from scraper.pararius import ParariusScraper
from tests.scraper.conftest import mock_scrape_url_content


@pytest.fixture
def realty_query() -> RealtyQuery:
    return RealtyQuery(
        name="Pararius: houses and apartments",
        ntfy_topic="pararius",
        cron_schedule="* * * * *",
        query_url="https://www.pararius.nl/koopwoningen/nederland/50m2",
        max_listing_page_number=999,
    )


@pytest.fixture
def scraper_detected_url() -> str:
    return "https://www.pararius.nl/scraper-detected"


def test_scrape_last_page_number(mocker: MockerFixture, realty_query: RealtyQuery):
    mocker.patch.object(ParariusScraper, "_connect_browser")
    mocker.patch.object(ParariusScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        pararius_scraper = ParariusScraper(
            playwright,
            query_name=realty_query.name,
            query_url=realty_query.query_url,
            max_listing_page_number=realty_query.max_listing_page_number,
        )
        last_page_number = pararius_scraper._get_last_page()

    assert last_page_number == 66


def test_scrape_first_page(mocker: MockerFixture, realty_query: RealtyQuery):
    mocker.patch.object(ParariusScraper, "_connect_browser")
    mocker.patch.object(ParariusScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)

    with sync_playwright() as playwright:
        pararius_scraper = ParariusScraper(
            playwright,
            query_name=realty_query.name,
            query_url=realty_query.query_url,
            max_listing_page_number=realty_query.max_listing_page_number,
        )
        results = pararius_scraper.get_page_results(page_number=1)

    assert len(results) == 30
    results.sort(key=lambda r: r.title)

    assert results[0].detail_url == "https://www.pararius.nl/huis-te-koop/almere/f38b9ba5/anjerstraat"
    assert results[0].query_name == "Pararius: houses and apartments"
    assert results[0].title == "Anjerstraat 2"
    assert results[0].price == "€\xa0535.000 k.k."
    assert (
        results[0].image_url
        == "https://casco-media-prod.global.ssl.fastly.net/f38b9ba5-f633-53a2-9faa-5567b338ad95/0fe81198ea5b1d64d0847a13051ea932.jpg?width=600&auto=webp"
    )
