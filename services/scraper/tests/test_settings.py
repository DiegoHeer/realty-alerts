import pytest

from scraper.enums import ScrapeMode
from scraper.settings import Settings


def test_settings_list_mode_no_detail_fields_required(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.delenv("SCRAPE_MODE", raising=False)

    settings = Settings()

    assert settings.scrape_mode == ScrapeMode.LIST
    assert settings.detail_url is None
    assert settings.listing_id is None


def test_settings_detail_mode_requires_detail_url(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("LISTING_ID", "42")
    monkeypatch.delenv("DETAIL_URL", raising=False)

    with pytest.raises(Exception, match="detail_url is required"):
        Settings()


def test_settings_detail_mode_requires_listing_id(monkeypatch):
    monkeypatch.setenv("WEBSITE", "funda")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("DETAIL_URL", "https://example.com/listing/1")
    monkeypatch.delenv("LISTING_ID", raising=False)

    with pytest.raises(Exception, match="listing_id is required"):
        Settings()


def test_settings_detail_mode_valid_when_all_fields_present(monkeypatch):
    monkeypatch.setenv("WEBSITE", "vastgoed_nl")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("DETAIL_URL", "https://example.com/listing/1")
    monkeypatch.setenv("LISTING_ID", "42")

    settings = Settings()

    assert settings.scrape_mode == ScrapeMode.DETAIL
    assert settings.detail_url == "https://example.com/listing/1"
    assert settings.listing_id == 42
