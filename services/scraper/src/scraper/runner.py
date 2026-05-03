import sys
from datetime import UTC, datetime

from loguru import logger

from scraper.bag import BagMatch, BagMissReason, ParquetBagLookup, apply_bag_match
from scraper.client import BackendClient
from scraper.enums import Website
from scraper.fetch.http import HttpFetch
from scraper.fetch.playwright import PlaywrightFetch
from scraper.models import DeadListing, Listing
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
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)

    website = Website(settings.website)
    logger.info(f"Starting scraper for {website}")

    # Initialize backend client
    client = BackendClient(base_url=settings.backend_api_url, api_key=settings.realty_api_key)
    if not client.health_check():
        logger.error("Backend API is unreachable — aborting")
        sys.exit(1)

    # Get last successful run timestamp
    since = client.get_last_successful_run(website)
    logger.info(f"Last successful run: {since or 'never'}")

    # Initialize fetch strategy
    if website in [Website.FUNDA, Website.PARARIUS]:
        fetch: HttpFetch | PlaywrightFetch = PlaywrightFetch(browser_url=settings.browser_url)
    else:
        fetch = HttpFetch()

    started_at = datetime.now(UTC)
    error_message = None
    matched_listings: list[Listing] = []
    dead_listings: list[DeadListing] = []

    try:
        with fetch:
            scraper_class = SCRAPER_MAP[website]
            scraper = scraper_class(fetch=fetch)
            listings = scraper.scrape(since=since)
            logger.info(f"Scraped {len(listings)} listings from {website}")

            with ParquetBagLookup() as bag:
                for listing in listings:
                    result = bag.lookup(
                        street=listing.street,
                        house_number=listing.house_number,
                        house_letter=listing.house_letter,
                        house_number_suffix=listing.house_number_suffix,
                        postcode=listing.postcode,
                        city=listing.city,
                    )
                    if isinstance(result, BagMatch):
                        apply_bag_match(listing, result)
                        matched_listings.append(listing)
                    else:
                        reason = _classify_dead_reason(listing, result)
                        dead_listings.append(DeadListing(listing=listing, reason=reason))
    except Exception as e:
        error_message = str(e)
        logger.exception(f"Scraping failed for {website}")
    finally:
        finished_at = datetime.now(UTC)

    # Submit results to backend API
    try:
        client.submit_results(
            website=website,
            listings=matched_listings,
            dead_listings=dead_listings,
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


def _classify_dead_reason(listing: Listing, bag_reason: BagMissReason) -> str:
    # house_number is mandatory for any successful parse — when it's missing
    # the parser didn't recognise the title at all, which is a different
    # failure mode than "BAG didn't have the address". Surface that
    # distinction in the DLQ so triage can focus on the right source.
    if listing.house_number is None:
        return "parse_failed"
    return bag_reason.value
