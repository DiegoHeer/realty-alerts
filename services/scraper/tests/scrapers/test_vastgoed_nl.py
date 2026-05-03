from scraper.enums import ListingStatus


def test_scrape_first_page(vastgoed_nl_scraper):
    listings = vastgoed_nl_scraper._scrape_page(page_number=1)

    assert len(listings) > 0
    assert all(listing.website == "vastgoed_nl" for listing in listings)
    assert all(listing.detail_url for listing in listings)
    assert all(listing.title for listing in listings)
    assert all(listing.status == ListingStatus.NEW for listing in listings)


def test_address_fields_populated(vastgoed_nl_scraper):
    listings = vastgoed_nl_scraper._scrape_page(page_number=1)

    # Cards expose street + city; postcode is not on the card so stays None.
    for listing in listings:
        assert listing.street, f"missing street for {listing.detail_url}"
        assert listing.house_number is not None, f"missing house_number for {listing.detail_url}"
        assert listing.city and listing.city != "unknown", f"city should come from span.city, got {listing.city!r}"
        assert listing.postcode is None, f"unexpected postcode for {listing.detail_url}"


def test_first_card_specifics(vastgoed_nl_scraper):
    listings = vastgoed_nl_scraper._scrape_page(page_number=1)
    first = listings[0]

    assert first.title == "Smaragdhorst 100"
    assert first.street == "Smaragdhorst"
    assert first.house_number == 100
    assert first.house_number_suffix is None
    assert first.city == "'s-Gravenhage"
