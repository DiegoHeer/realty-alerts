from scraper.scrapers.pararius import ParariusScraper
from conftest import MockFetch


def test_scrape_last_page_number():
    scraper = ParariusScraper(fetch=MockFetch(), base_url="https://www.pararius.nl/koopwoningen/nederland/50m2")
    last_page = scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES


def test_scrape_first_page():
    scraper = ParariusScraper(fetch=MockFetch(), base_url="https://www.pararius.nl/koopwoningen/nederland/50m2")
    listings = scraper._scrape_page(page_number=1)

    assert len(listings) == 30
    listings.sort(key=lambda r: r.title)

    assert listings[0].detail_url == "https://www.pararius.nl/huis-te-koop/almere/f38b9ba5/anjerstraat"
    assert listings[0].title == "Anjerstraat 2"
    assert listings[0].price == "€\xa0535.000 k.k."
    assert listings[0].website == "pararius"
