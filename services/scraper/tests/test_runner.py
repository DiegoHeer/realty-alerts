from unittest.mock import MagicMock, patch

import pytest

from scraper.enums import ScrapeMode
from scraper.runner import run


def test_run_dispatches_to_run_list_in_list_mode(monkeypatch):
    monkeypatch.setenv("WEBSITE", "vastgoed_nl")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.setenv("SCRAPE_MODE", "list")

    with patch("scraper.runner._run_list") as mock_list, patch("scraper.runner._run_detail") as mock_detail:
        run()

    mock_list.assert_called_once()
    mock_detail.assert_not_called()


def test_run_dispatches_to_run_detail_in_detail_mode(monkeypatch):
    monkeypatch.setenv("WEBSITE", "vastgoed_nl")
    monkeypatch.setenv("REALTY_API_KEY", "testkey")
    monkeypatch.setenv("SCRAPE_MODE", "detail")
    monkeypatch.setenv("DETAIL_URL", "https://example.com/listing/1")
    monkeypatch.setenv("LISTING_ID", "42")

    with patch("scraper.runner._run_list") as mock_list, patch("scraper.runner._run_detail") as mock_detail:
        run()

    mock_detail.assert_called_once()
    mock_list.assert_not_called()
