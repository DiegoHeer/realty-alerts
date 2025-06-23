import logging
import textwrap
from pathlib import Path

from celery import Celery
from playwright.sync_api import sync_playwright

from enums import QueryResultORMStatus
from models import RealtyQuery
from notifications import (
    notify_about_new_results,
    notify_about_successful_startup,
    notify_when_there_are_no_new_listings,
)
from queries import load_queries
from scheduler import CeleryConfig
from scraper.funda import FundaScraper
from storage import get_new_query_results, save_query_results, setup_database, update_query_results_status

LOGGER = logging.getLogger(__name__)
QUERIES_DIR = Path(__file__).resolve().parents[1] / "queries"

realty_queries = load_queries(QUERIES_DIR)

app = Celery("tasks")
app.config_from_object(CeleryConfig(realty_queries))
app.autodiscover_tasks()

setup_database()

notify_about_successful_startup(realty_queries)


@app.task(pydantic=True)
def main(realty_query: RealtyQuery) -> None:
    LOGGER.info(f"The query url is: {textwrap.shorten(realty_query.query_url, width=100, placeholder='...')}")
    LOGGER.info(f"The url used to send Realty-Alerts notifications is: {realty_query.notification_url}")

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, realty_query)
        query_results = funda_scraper.get_query_results()

    save_query_results(query_results)

    new_query_results = get_new_query_results()
    notify_about_new_results(realty_query.notification_url, new_query_results)

    update_query_results_status(new_query_results, status=QueryResultORMStatus.NOTIFIED)

    if not new_query_results and realty_query.notify_if_no_new_listing:
        notify_when_there_are_no_new_listings(realty_query)
