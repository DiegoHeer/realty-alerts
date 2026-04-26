from pathlib import Path

MOCK_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def test_get_last_page_capped_at_max(funda_scraper):
    last_page = funda_scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES (fixture exposes pages up to 666)


def test_scrape_detail_urls_filters_to_detail_pattern(funda_scraper, monkeypatch):
    monkeypatch.setattr(funda_scraper, "MAX_PAGES", 2)
    urls = funda_scraper._scrape_detail_urls()

    assert len(urls) > 0
    assert all(url.startswith("https://www.funda.nl/detail/") for url in urls)


def test_scrape_detail_page_extracts_fields(funda_scraper):
    detail_url = "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/"
    listing = funda_scraper._scrape_detail_page(detail_url)

    assert listing is not None
    assert listing.detail_url == detail_url
    assert listing.title == "Bangert 58"
    assert listing.price == "€ 775.000 k.k."
    assert listing.city == "blokker"
    assert listing.image_url and listing.image_url.startswith("https://")
    assert listing.website == "funda"


def test_is_scraping_detected_true_when_blocked(funda_scraper):
    blocked_html = (MOCK_DATA_DIR / "funda_scraper_detected.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(blocked_html) is True


def test_is_scraping_detected_false_for_normal_page(funda_scraper):
    normal_html = (MOCK_DATA_DIR / "funda_detail.html").read_text(encoding="utf-8")
    assert funda_scraper.is_scraping_detected(normal_html) is False
