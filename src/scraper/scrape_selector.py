from enums import Websites
from scraper.base import BaseScraper
from scraper.funda import FundaScraper
from scraper.pararius import ParariusScraper
from scraper.vastgoed_nl import VastgoedNLScraper


def get_scraper_class(website: Websites) -> type[BaseScraper]:
    mapping = {
        Websites.FUNDA: FundaScraper,
        Websites.PARARIUS: ParariusScraper,
        Websites.VASTGOED_NL: VastgoedNLScraper,
    }

    try:
        return mapping[website]
    except KeyError:
        raise KeyError(f"There is no scraper available for website: {website.value}")
