from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from enums import ScrapeStrategy, Websites
from models import QueryResult
from scraper.base import BaseScraper


class FundaScraper(BaseScraper):
    website = Websites.FUNDA
    scrape_strategy = ScrapeStrategy.PLAYWRIGHT

    def get_query_results(self) -> list[QueryResult]:
        detail_urls = self.scrape_detail_urls_of_listing_page()
        return [self.scrape_detail_page(url) for url in detail_urls]

    def scrape_detail_urls_of_listing_page(self) -> set[str]:
        stop_range = self._get_last_page() + 1
        return {url for page_number in range(1, stop_range) for url in self._scrape_urls_per_page_number(page_number)}

    def _get_last_page(self) -> int:
        hrefs = self._get_all_hrefs(self.query_url)
        page_hrefs = [href for href in hrefs if "?page" in href]
        page_numbers = [int(href.split("=")[1]) for href in page_hrefs]

        max_page_number = max(page_numbers) if page_numbers else 1

        return min(max_page_number, self.max_listing_page_number)

    def _scrape_urls_per_page_number(self, page_number: int) -> list[str]:
        page_url = self._append_page_number_to_url(self.query_url, page_number)
        hrefs = self._get_all_hrefs(page_url)
        return self._filter_and_build_detail_urls(hrefs)

    def _get_all_hrefs(self, page_url: str) -> list[str]:
        soup = self.get_url_soup(page_url)
        return [str(link.get("href")) for link in soup.select("a")]

    @staticmethod
    def _append_page_number_to_url(url: str, page_number: int) -> str:
        parsed_url = urlparse(url=url)
        query_params = parse_qs(parsed_url.query)

        query_params["search_result"] = [str(page_number)]

        new_query = urlencode(query_params, doseq=True, quote_via=quote)
        return urlunparse(parsed_url._replace(query=new_query))

    def is_scraping_detected(self, content: str) -> bool:
        return "Je bent bijna op de pagina die je zoekt" in content

    def _filter_and_build_detail_urls(self, hrefs: list[str]) -> list[str]:
        filtered_hrefs = [href for href in hrefs if "detail" in href]
        return [f"https://{self.website.value}{href}" for href in filtered_hrefs]

    def scrape_detail_page(self, detail_url: str) -> QueryResult:
        soup = self.get_url_soup(detail_url)

        title = self._get_detail_page_title(soup)
        price = self._get_detail_page_price(soup)
        image_url = self._get_detail_page_image_url(soup)

        return QueryResult(detail_url=detail_url, title=title, price=price, image_url=image_url)

    def _get_detail_page_title(self, soup: BeautifulSoup) -> str:
        title_element = soup.select_one("h1 span.block.text-2xl.font-bold")
        return "" if title_element is None else title_element.get_text()

    def _get_detail_page_price(self, soup: BeautifulSoup) -> str:
        price_element = soup.select_one("div.flex.gap-2.font-bold > span")
        return "" if price_element is None else price_element.get_text()

    def _get_detail_page_image_url(self, soup: BeautifulSoup) -> str:
        if img_element := soup.select_one("img.size-full.object-cover"):
            return str(img_element.get("src")) or ""
        return ""
