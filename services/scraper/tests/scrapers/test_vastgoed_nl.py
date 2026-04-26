def test_scrape_first_page(vastgoed_nl_scraper):
    listings = vastgoed_nl_scraper._scrape_page(page_number=1)

    assert len(listings) > 0
    assert all(listing.website == "vastgoed_nl" for listing in listings)
    assert all(listing.detail_url for listing in listings)
    assert all(listing.title for listing in listings)
