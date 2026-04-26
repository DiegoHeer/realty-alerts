from datetime import datetime
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup
from loguru import logger

from scraper.enums import Website
from scraper.models import Listing
from scraper.protocols import FetchStrategy
from scraper.scrapers.base import BaseScraper


class FundaScraper(BaseScraper):
    website = Website.FUNDA
    MAX_PAGES = 5

    def __init__(self, fetch: FetchStrategy, base_url: str = "https://www.funda.nl/zoeken/koop") -> None:
        super().__init__(fetch)
        self.base_url = base_url

    def scrape(self, since: datetime | None) -> list[Listing]:
        logger.info(f"Scraping Funda (since={since})")
        detail_urls = self._scrape_detail_urls()
        listings = [self._scrape_detail_page(url) for url in detail_urls]
        return [listing for listing in listings if listing is not None]

    def _scrape_detail_urls(self) -> set[str]:
        last_page = self._get_last_page()
        urls: set[str] = set()
        for page_number in range(1, last_page + 1):
            page_url = self._append_page_number(self.base_url, page_number)
            soup = self.get_soup(page_url)
            hrefs = [str(link.get("href")) for link in soup.select("a")]
            detail_hrefs = [href for href in hrefs if href.startswith("/detail/")]
            urls.update(f"https://www.funda.nl{href}" for href in detail_hrefs)
        logger.info(f"Found {len(urls)} detail URLs across {last_page} pages")
        return urls

    def _get_last_page(self) -> int:
        soup = self.get_soup(self.base_url)
        hrefs = [str(link.get("href")) for link in soup.select("a")]
        page_hrefs = [href for href in hrefs if "?page" in href]
        page_numbers = []
        for href in page_hrefs:
            try:
                page_numbers.append(int(href.split("=")[1]))
            except (ValueError, IndexError):
                continue
        max_page = max(page_numbers) if page_numbers else 1
        return min(max_page, self.MAX_PAGES)

    @staticmethod
    def _append_page_number(url: str, page_number: int) -> str:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        params["search_result"] = [str(page_number)]
        new_query = urlencode(params, doseq=True, quote_via=quote)
        return urlunparse(parsed._replace(query=new_query))

    def _scrape_detail_page(self, detail_url: str) -> Listing | None:
        try:
            soup = self.get_soup(detail_url)
        except Exception:
            logger.warning(f"Failed to scrape detail page: {detail_url}")
            return None

        title = self._get_text(soup, "h1 span.block.text-2xl.font-bold")
        price = self._get_text(soup, "div.flex.gap-2.font-bold > span")
        image_url = self._get_attr(soup, "img.size-full.object-cover", "src")

        return Listing(
            detail_url=detail_url,
            title=title,
            price=price,
            city=self._extract_city_from_url(detail_url),
            image_url=image_url or None,
            website=self.website,
        )

    def is_scraping_detected(self, content: str) -> bool:
        return "Je bent bijna op de pagina die je zoekt" in content

    @staticmethod
    def _extract_city_from_url(url: str) -> str:
        parts = urlparse(url).path.strip("/").split("/")
        # URL pattern: /detail/<koop|huur>/<city>/<slug>/<id>/
        return parts[2] if len(parts) > 2 else "unknown"

    @staticmethod
    def _get_text(soup: BeautifulSoup, selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text().strip() if el else ""

    @staticmethod
    def _get_attr(soup: BeautifulSoup, selector: str, attr: str) -> str:
        el = soup.select_one(selector)
        return str(el.get(attr, "")) if el else ""
