import sys
from datetime import UTC, datetime
from typing import cast

import httpx
from loguru import logger

from scraper.client import BackendClient
from scraper.enums import ScrapeMode, Website
from scraper.fetch.http import HttpFetch
from scraper.fetch.playwright import PlaywrightFetch
from scraper.models import Listing
from scraper.protocols import DetailScraper, FetchStrategy
from scraper.scrapers.base import ScrapingException
from scraper.scrapers.funda import FundaScraper
from scraper.scrapers.pararius import ParariusScraper
from scraper.scrapers.vastgoed_nl import VastgoedNLScraper
from scraper.settings import Settings

PORTAL_SCRAPER_MAP = {
    Website.FUNDA: FundaScraper,
    Website.PARARIUS: ParariusScraper,
    Website.VASTGOED_NL: VastgoedNLScraper,
}


def run() -> None:
    settings = Settings()
    _configure_logging(settings.log_level)
    website = Website(settings.website)
    if settings.scrape_mode == ScrapeMode.DETAIL:
        _run_detail(
            website=website,
            detail_url=cast(str, settings.detail_url),
            listing_id=cast(int, settings.listing_id),
            backend_api_url=settings.backend_api_url,
            realty_api_key=settings.realty_api_key,
            browser_url=settings.browser_url,
        )
    else:
        _run_list(
            website=website,
            backend_api_url=settings.backend_api_url,
            realty_api_key=settings.realty_api_key,
            browser_url=settings.browser_url,
        )


def _run_list(
    website: Website,
    backend_api_url: str,
    realty_api_key: str,
    browser_url: str,
) -> None:
    logger.info(f"Starting list scraper for {website}")

    client = BackendClient(base_url=backend_api_url, api_key=realty_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    since = client.get_last_successful_run(website)
    logger.info(f"Last successful run: {since or 'never'}")

    started_at = datetime.now(UTC)
    error_message: str | None = None
    listings: list[Listing] = []

    try:
        with _make_fetch(website, browser_url) as fetch:
            scraper = PORTAL_SCRAPER_MAP[website](fetch=fetch)
            listings = scraper.scrape_list(since=since)
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

    logger.info(f"List scraper for {website} completed successfully")


def _run_detail(
    website: Website,
    detail_url: str,
    listing_id: int,
    backend_api_url: str,
    realty_api_key: str,
    browser_url: str,
) -> None:
    logger.info(f"Starting detail scraper for {website}, listing_id={listing_id}")

    client = BackendClient(base_url=backend_api_url, api_key=realty_api_key)

    try:
        with _make_fetch(website, browser_url) as fetch:
            scraper = cast(DetailScraper, PORTAL_SCRAPER_MAP[website](fetch=fetch))
            detail = scraper.scrape_detail(detail_url)
            logger.info(f"Scraped detail for listing {listing_id} from {website}")
    except ScrapingException as exc:
        logger.error(f"Bot detection triggered for listing {listing_id}: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.exception(f"Detail scraping failed for listing {listing_id}: {exc}")
        sys.exit(1)

    try:
        client.submit_detail_result(listing_id=listing_id, detail=detail)
    except httpx.HTTPError as exc:
        logger.error(f"Failed to submit detail result for listing {listing_id}: {exc}")
        sys.exit(1)

    logger.info(f"Detail scraper for listing {listing_id} completed successfully")


def _configure_logging(level: str) -> None:
    logger.remove()
    logger.add(sys.stderr, level=level)


def _make_fetch(website: Website, browser_url: str) -> FetchStrategy:
    # Funda and Pararius hide listing markup behind client-side rendering,
    # so they need a real browser. VastgoedNL serves rendered HTML and runs
    # fine over plain HTTP.
    if website in {Website.FUNDA, Website.PARARIUS}:
        return PlaywrightFetch(browser_url=browser_url)
    return HttpFetch()
