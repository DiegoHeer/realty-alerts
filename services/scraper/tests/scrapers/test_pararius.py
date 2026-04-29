def test_scrape_last_page_number(pararius_scraper):
    last_page = pararius_scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES


def test_scrape_first_page(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert len(listings) == 30
    listings.sort(key=lambda r: r.title)

    assert listings[0].detail_url == "https://www.pararius.nl/huis-te-koop/doetinchem/1b755539/alpen"
    assert listings[0].title == "Alpen 10"
    assert listings[0].price == "€\xa0695.000 k.k."
    assert listings[0].city == "doetinchem"
    assert listings[0].website == "pararius"


def test_titles_are_non_empty(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert listings, "fixture should yield listings"
    for listing in listings:
        assert listing.title, f"empty title for {listing.detail_url}"


def test_image_urls_are_http_or_none(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert listings, "fixture should yield listings"
    for listing in listings:
        assert listing.image_url is None or listing.image_url.startswith(("http://", "https://"))
