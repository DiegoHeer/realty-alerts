def test_scrape_last_page_number(pararius_scraper):
    last_page = pararius_scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES


def test_scrape_first_page(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert len(listings) == 30
    listings.sort(key=lambda r: r.title)

    assert listings[0].detail_url == "https://www.pararius.nl/huis-te-koop/almere/f38b9ba5/anjerstraat"
    assert listings[0].title == "Anjerstraat 2"
    assert listings[0].price == "€\xa0535.000 k.k."
    assert listings[0].website == "pararius"
