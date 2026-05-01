from pathlib import Path

import pytest

from scraper.scrapers.funda import FundaScraper

MOCK_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_get_last_page_capped_at_max(funda_scraper):
    last_page = funda_scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES (fixture exposes pages up to 666)


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ('<a href="?page=3">3</a>', 3),
        ('<a href="?page=3&utm_source=foo">3</a>', 3),  # extra query params
        ('<a href="/zoeken/koop?utm_source=foo&page=4">4</a>', 4),  # page not first param
        ('<a href="?page=abc">x</a><a href="?page=2">2</a>', 2),  # malformed entry skipped
        # No hydrated pagination → speculatively scan up to MAX_PAGES (5).
        ("<a>nothing</a>", 5),
    ],
)
def test_get_last_page_parses_query_string(html, expected):
    class _Fetch:
        def fetch(self, url: str) -> str:
            return f"<html><body>{html}</body></html>"

        def close(self) -> None:
            pass

    scraper = FundaScraper(fetch=_Fetch(), base_url="https://www.funda.nl/zoeken/koop")
    assert scraper._get_last_page() == expected


def test_scrape_yields_listings(funda_scraper, monkeypatch):
    monkeypatch.setattr(funda_scraper, "MAX_PAGES", 2)
    listings = funda_scraper.scrape(since=None)

    assert len(listings) > 0
    for listing in listings:
        assert listing.detail_url.startswith("https://www.funda.nl/detail/")
        assert listing.title, f"missing title for {listing.detail_url}"
        assert listing.price.startswith("€"), f"unexpected price for {listing.detail_url}: {listing.price!r}"
        assert listing.street, f"missing street for {listing.detail_url}"
        assert listing.house_number is not None, f"missing house_number for {listing.detail_url}"
        assert listing.postcode, f"missing postcode for {listing.detail_url}"
        assert listing.city and listing.city != "unknown", f"missing city for {listing.detail_url}"
        assert listing.image_url and listing.image_url.startswith("https://cloud.funda.nl"), (
            f"unexpected image_url for {listing.detail_url}: {listing.image_url!r}"
        )
        assert listing.website == "funda"


def test_scrape_specific_card(funda_scraper, monkeypatch):
    monkeypatch.setattr(funda_scraper, "MAX_PAGES", 2)
    listings = funda_scraper.scrape(since=None)

    heerhugowaard = next(
        listing
        for listing in listings
        if listing.detail_url == "https://www.funda.nl/detail/koop/heerhugowaard/huis-madeliefstraat-5/43339393/"
    )
    assert heerhugowaard.title == "Madeliefstraat 5"
    assert heerhugowaard.price == "€ 720.000 k.k."
    assert heerhugowaard.street == "Madeliefstraat"
    assert heerhugowaard.house_number == 5
    assert heerhugowaard.house_number_suffix is None
    assert heerhugowaard.postcode == "1706 AN"
    assert heerhugowaard.city == "Heerhugowaard"
    assert heerhugowaard.image_url == "https://cloud.funda.nl/valentina_media/207/398/277.jpg?options=width=228"


def test_is_scraping_detected_true_when_blocked(funda_scraper):
    blocked_html = (MOCK_DATA_DIR / "funda_scraper_detected.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(blocked_html) is True


def test_is_scraping_detected_false_for_normal_page(funda_scraper):
    normal_html = (MOCK_DATA_DIR / "funda_listing.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(normal_html) is False
