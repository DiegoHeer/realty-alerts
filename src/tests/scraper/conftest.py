from pathlib import Path

MOCK_DATA_DIR = Path(__file__).resolve().parent / "data"


def mock_scrape_url_content(url: str) -> str:
    url_to_file_name = {
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22,%22apartment%22%5D": "funda_listing",
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=1": "funda_1",
        "https://www.funda.nl/zoeken/koop?object_type=%5B%22house%22%2C%22apartment%22%5D&search_result=2": "funda_2",
        "https://www.funda.nl/detail/koop/blokker/huis-bangert-58/43063167/": "funda_detail",
        "https://www.funda.nl/scraper-detected": "funda_scraper_detected",
        "https://www.pararius.nl/koopwoningen/nederland/50m2": "pararius_listing",
        "https://www.pararius.nl/koopwoningen/nederland/50m2/page-1": "pararius_listing",
        "https://www.pararius.nl/scraper-detected": "pararius_scraper_detected",
        "https://aanbod.vastgoednederland.nl/koopwoningen?q=den+haag": "vastgoed_nl_listing",
        "https://aanbod.vastgoednederland.nl/koopwoningen?q=den%20haag&p=1": "vastgoed_nl_listing",
        "https://aanbod.vastgoednederland.nl/scraper-detected": "vastgoed_nl_scraper_detected",
    }

    try:
        return _load_html_file(file_name=f"{url_to_file_name[url]}.html")
    except KeyError:
        raise KeyError(f"No mock defined for URL: {url}")


def _load_html_file(file_name: str) -> str:
    file_path = MOCK_DATA_DIR / file_name
    return file_path.read_text(encoding="utf-8")
