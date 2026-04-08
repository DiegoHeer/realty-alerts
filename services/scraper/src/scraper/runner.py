import sys
from datetime import UTC, datetime

from loguru import logger

from scraper.client import BackendClient
from scraper.enums import Website
from scraper.fetch.http import HttpFetch
from scraper.fetch.playwright import PlaywrightFetch
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
    settings = Settings()  # type: ignore[call-arg]
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    website = Website(settings.website)
    logger.info(f"Starting scraper for {website}")

    # Initialize backend client
    client = BackendClient(base_url=settings.backend_api_url, api_key=settings.scraper_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    # Get last successful run timestamp
    since = client.get_last_successful_run(website)
    logger.info(f"Last successful run: {since or 'never'}")

    # Initialize fetch strategy
    if website == Website.FUNDA:
        fetch = PlaywrightFetch(browser_url=settings.browser_url)
    else:
        fetch = HttpFetch()

    # Create scraper and run
    scraper_class = SCRAPER_MAP[website]
    scraper = scraper_class(fetch=fetch)

    started_at = datetime.now(UTC)
    error_message = None
    listings = []

    try:
        listings = scraper.scrape(since=since)
        logger.info(f"Scraped {len(listings)} listings from {website}")
    except Exception as e:
        error_message = str(e)
        logger.exception(f"Scraping failed for {website}")
    finally:
        finished_at = datetime.now(UTC)
        fetch.close()

    # Submit results to backend API
    try:
        client.submit_results(
            website=website,
            listings=listings,
            started_at=started_at,
            finished_at=finished_at,
            error_message=error_message,
        )
    except Exception:
        logger.exception("Failed to submit results to backend API")
        sys.exit(1)

    if error_message:
        sys.exit(1)

    logger.info(f"Scraper for {website} completed successfully")
