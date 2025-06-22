import logging
from pathlib import Path

from celery import Celery
from playwright.sync_api import sync_playwright

from models import RealtyQuery
from notifications import send_notifications
from queries import load_queries
from scraper.funda import FundaScraper
from settings import SETTINGS, CeleryConfig
from storage import get_new_query_results, save_query_results, setup_database

LOGGER = logging.getLogger(__name__)
QUERIES_DIR = Path(__file__).resolve().parents[1] / "queries"

realty_queries = load_queries(QUERIES_DIR)

app = Celery("tasks")
app.config_from_object(CeleryConfig(realty_queries))
app.autodiscover_tasks()

setup_database()


@app.task(pydantic=True)
def main(realty_query: RealtyQuery) -> None:
    LOGGER.info(f"The query url is: {realty_query.query_url}")
    LOGGER.info(f"The NTFY url to access Realty-Alerts notifications is: {SETTINGS.ntfy_url}")

    with sync_playwright() as playwright:
        funda_scraper = FundaScraper(playwright, realty_query)
        query_results = funda_scraper.get_query_results()

    save_query_results(query_results)

    new_query_results = get_new_query_results()
    send_notifications(new_query_results)
