import sys
from datetime import UTC, datetime

from loguru import logger

from scraper.client import BackendClient
from scraper.enums import Website
from scraper.fetch.http import HttpFetch
from scraper.fetch.playwright import PlaywrightFetch
from scraper.models import Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.funda import FundaScraper
from scraper.scrapers.pararius import ParariusScraper
from scraper.scrapers.vastgoed_nl import VastgoedNLScraper
from scraper.settings import Settings

SCRAPER_MAP = {
    Website.FUNDA: FundaScraper,
    Website.PARARIUS: ParariusScraper,
    Website.VASTGOED_NL: VastgoedNLScraper,
}


def run() -> None:
    settings = Settings()
    _configure_logging(settings.log_level)

    website = Website(settings.website)
    logger.info(f"Starting scraper for {website}")

    client = BackendClient(base_url=settings.backend_api_url, api_key=settings.realty_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    since = client.get_last_successful_run(website)
    logger.info(f"Last successful run: {since or 'never'}")

    started_at = datetime.now(UTC)
    error_message: str | None = None
    listings: list[Listing] = []

    try:
        with _make_fetch(website, settings) as fetch:
            scraper = SCRAPER_MAP[website](fetch=fetch)
            listings = scraper.scrape(since=since)
            logger.info(f"Scraped {len(listings)} listings from {website}")
    except Exception as exc:
        error_message = str(exc)
        logger.exception(f"Scraping failed for {website}")

    finished_at = datetime.now(UTC)

    try:
        client.submit_results(
            website=website,
            listings=listings,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
        )
    except Exception as exc:
        logger.exception(f"Failed to submit results to backend API: {exc}")
        sys.exit(1)

    if error_message:
        sys.exit(1)

    logger.info(f"Scraper for {website} completed successfully")


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)


def _make_fetch(website: Website, settings: Settings) -> FetchStrategy:
    # Funda and Pararius hide listing markup behind client-side rendering,
    # so they need a real browser. VastgoedNL serves rendered HTML and runs
    # fine over plain HTTP.
    if website in {Website.FUNDA, Website.PARARIUS}:
        return PlaywrightFetch(browser_url=settings.browser_url)
    return HttpFetch()
