from pathlib import Path

import pytest

from scraper.scrapers.funda import FundaScraper, _CardAddress

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
        ("<a>nothing</a>", 1),  # default when no pagination
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


def test_scrape_listing_pages_yields_card_addresses(funda_scraper, monkeypatch):
    monkeypatch.setattr(funda_scraper, "MAX_PAGES", 2)
    cards = funda_scraper._scrape_listing_pages()

    assert len(cards) > 0
    for url, addr in cards.items():
        assert url.startswith("https://www.funda.nl/detail/")
        assert addr.street, f"missing street for {url}"
        assert addr.house_number is not None, f"missing house_number for {url}"
        assert addr.postcode, f"missing postcode for {url}"
        assert addr.city and addr.city != "unknown", f"missing city for {url}"


def test_scrape_listing_pages_specific_card(funda_scraper, monkeypatch):
    monkeypatch.setattr(funda_scraper, "MAX_PAGES", 2)
    cards = funda_scraper._scrape_listing_pages()

    haarlem = cards["https://www.funda.nl/detail/koop/haarlem/huis-delftlaan-265/43063127/"]
    assert haarlem.street == "Delftlaan"
    assert haarlem.house_number == 265
    assert haarlem.house_number_suffix is None
    assert haarlem.postcode == "2024 CB"
    assert haarlem.city == "Haarlem"


def test_scrape_detail_page_merges_card_address(funda_scraper):
    detail_url = "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"
    address = _CardAddress(
        street="Bangert",
        house_number=58,
        house_number_suffix=None,
        postcode="1695 BB",
        city="Blokker",
    )

    listing = funda_scraper._scrape_detail_page(detail_url, address)

    assert listing is not None
    assert listing.detail_url == detail_url
    assert listing.title == "Bangert 58"
    assert listing.price == "€ 775.000 k.k."
    assert listing.city == "Blokker"
    assert listing.street == "Bangert"
    assert listing.house_number == 58
    assert listing.postcode == "1695 BB"
    assert listing.image_url and listing.image_url.startswith("https://")
    assert listing.website == "funda"


def test_is_scraping_detected_true_when_blocked(funda_scraper):
    blocked_html = (MOCK_DATA_DIR / "funda_scraper_detected.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(blocked_html) is True


def test_is_scraping_detected_false_for_normal_page(funda_scraper):
    normal_html = (MOCK_DATA_DIR / "funda_detail.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(normal_html) is False
