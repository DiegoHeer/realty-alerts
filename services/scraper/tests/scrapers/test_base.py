import pytest

from scraper.scrapers.base import BaseScraper, ScrapingException


class _StubFetch:
    def __init__(self, content: str) -> None:
        self.content = content

    def fetch(self, url: str) -> str:
        return self.content

    def close(self) -> None:
        pass


def test_no_markers_never_flags_block():
    scraper = BaseScraper(fetch=_StubFetch("<html>ok</html>"))
    assert scraper.is_scraping_detected("anything at all") is False


def test_marker_substring_flags_block():
    class MarkedScraper(BaseScraper):
        detection_markers = ("please verify you are human",)

    scraper = MarkedScraper(fetch=_StubFetch(""))
    assert scraper.is_scraping_detected("...please verify you are human...") is True
    assert scraper.is_scraping_detected("normal page body") is False


def test_get_soup_raises_when_marker_present():
    class MarkedScraper(BaseScraper):
        detection_markers = ("BLOCKED",)

    scraper = MarkedScraper(fetch=_StubFetch("<html>BLOCKED</html>"))
    with pytest.raises(ScrapingException, match="https://example.com"):
        scraper.get_soup("https://example.com")
