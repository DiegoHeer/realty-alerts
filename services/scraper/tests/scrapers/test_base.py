import pytest

from scraper.scrapers.base import BaseScraper, ScrapingException


def test_no_markers_never_flags_block(static_fetch):
    scraper = BaseScraper(fetch=static_fetch("<html>ok</html>"))
    assert scraper.is_scraping_detected("anything at all") is False


def test_marker_substring_flags_block(static_fetch):
    class MarkedScraper(BaseScraper):
        detection_markers = ("please verify you are human",)

    scraper = MarkedScraper(fetch=static_fetch(""))
    assert scraper.is_scraping_detected("...please verify you are human...") is True
    assert scraper.is_scraping_detected("normal page body") is False


def test_get_soup_raises_when_marker_present(static_fetch):
    class MarkedScraper(BaseScraper):
        detection_markers = ("BLOCKED",)

    scraper = MarkedScraper(fetch=static_fetch("<html>BLOCKED</html>"))
    with pytest.raises(ScrapingException, match="https://example.com"):
        scraper.get_soup("https://example.com")
