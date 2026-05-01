def test_scrape_last_page_number(pararius_scraper):
    last_page = pararius_scraper._get_last_page()
    assert last_page == 5  # capped by MAX_PAGES


def test_scrape_first_page(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert len(listings) == 30
    listings.sort(key=lambda r: r.title)

    first = listings[0]
    assert first.detail_url == "https://www.pararius.nl/huis-te-koop/doetinchem/1b755539/alpen"
    assert first.title == "Alpen 10"
    assert first.price == "€\xa0695.000 k.k."
    assert first.city == "Doetinchem"
    assert first.street == "Alpen"
    assert first.house_number == 10
    assert first.house_number_suffix is None
    assert first.postcode == "7007 LV"
    assert first.website == "pararius"


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


def test_address_fields_populated(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    # All cards in the fixture have a populated subtitle, so every listing
    # should carry a street + house_number + postcode + city.
    for listing in listings:
        assert listing.street, f"missing street for {listing.detail_url}"
        assert listing.house_number is not None, f"missing house_number for {listing.detail_url}"
        assert listing.postcode, f"missing postcode for {listing.detail_url}"
        assert listing.city and listing.city != "unknown", f"missing city for {listing.detail_url}"


def test_house_number_with_letter_suffix(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)
    by_title = {listing.title: listing for listing in listings}

    listing = by_title["Baarlosestraat 31 a"]
    assert listing.street == "Baarlosestraat"
    assert listing.house_number == 31
    assert listing.house_number_suffix == "a"
