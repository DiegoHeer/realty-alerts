from pathlib import Path

MOCK_DATA_DIR = Path(__file__).resolve().parent / "data"

URL_TO_FILE = {
    "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D": "funda_listing.html",
    "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=1": "funda_1.html",
    "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=2": "funda_2.html",
    "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/": "funda_detail.html",
    "https://www.funda.nl/scraper-detected": "funda_scraper_detected.html",
    "https://www.pararius.nl/koopwoningen/nederland/50m2": "pararius_listing.html",
    "https://www.pararius.nl/koopwoningen/nederland/50m2/page-1": "pararius_listing.html",
    "https://www.pararius.nl/scraper-detected": "pararius_scraper_detected.html",
    "https://aanbod.vastgoednederland.nl/koopwoningen?q=den+haag": "vastgoed_nl_listing.html",
    "https://aanbod.vastgoednederland.nl/koopwoningen?q=den%20haag&p=1": "vastgoed_nl_listing.html",
}


class MockFetch:
    """FetchStrategy implementation that returns local HTML files."""

    def fetch(self, url: str) -> str:
        if url not in URL_TO_FILE:
            raise KeyError(f"No mock defined for URL: {url}")
        file_path = MOCK_DATA_DIR / URL_TO_FILE[url]
        return file_path.read_text(encoding="utf-8")
