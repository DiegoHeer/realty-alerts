from pathlib import Path

from celery import Celery
from loguru import logger
from playwright.sync_api import sync_playwright

from enums import QueryResultStatus
from models import RealtyQuery
from notifications import (
    notify_about_new_results,
    notify_about_successful_startup,
    notify_when_there_are_no_new_listings,
)
from queries import load_queries
from scheduler import CeleryConfig
from scraper.scrape_selector import get_scraper_class
from storage import get_new_query_results, save_query_results, setup_database, update_query_results_status

QUERIES_DIR = Path(__file__).resolve().parents[1] / "queries"

realty_queries = load_queries(QUERIES_DIR)

app = Celery("tasks")
app.config_from_object(CeleryConfig(realty_queries))
app.autodiscover_tasks()

setup_database()

notify_about_successful_startup(realty_queries)


@app.task(pydantic=True)
def main(realty_query: RealtyQuery) -> None:
    logger.info(f"Start scraping for query: '{realty_query.name} ({realty_query.notification_url})'")

    scraper_class = get_scraper_class(website=realty_query.website)
    with sync_playwright() as playwright:
        scraper = scraper_class(
            playwright,
            query_name=realty_query.name,
            query_url=realty_query.query_url,
            max_listing_page_number=realty_query.max_listing_page_number,
        )
        query_results = scraper.get_query_results()

    save_query_results(query_results)

    new_query_results = get_new_query_results()
    notify_about_new_results(realty_query.notification_url, new_query_results)

    update_query_results_status(new_query_results, status=QueryResultStatus.NOTIFIED)

    if not new_query_results and realty_query.notify_if_no_new_listing:
        notify_when_there_are_no_new_listings(realty_query)
