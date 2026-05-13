from scraper.enums import ListingStatus
from scraper.models import DetailListing


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
    assert first.postcode == "7007LV"
    assert first.website == "pararius"


def test_titles_are_non_empty(pararius_scraper):
    listings = pararius_scraper._scrape_page(page_number=1)

    assert listings, "fixture should yield listings"
    for listing in listings:
        assert listing.title, f"empty title for {listing.detail_url}"
        assert listing.status == ListingStatus.NEW


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
    assert listing.house_letter == "a"
    assert listing.house_number_suffix is None


DETAIL_URL = "https://www.pararius.nl/huis-te-koop/rotterdam/cca868ff/vigohof"


def test_scrape_detail_returns_detail_listing(pararius_scraper):
    detail = pararius_scraper.scrape_detail(DETAIL_URL)

    assert isinstance(detail, DetailListing)
    assert detail.price == "Prijs op aanvraag"
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 == 114
    assert detail.room_count == 4
    assert detail.bedroom_count == 3
    assert detail.bathroom_count == 1
    assert detail.construction_period == "1981"
    assert detail.energy_label == "B"
    assert detail.postcode == "3067ZV"


def test_scrape_detail_returns_none_for_absent_fields(static_pararius_scraper):
    minimal_html = """
    <html><body>
    <div class="listing-detail-summary__price">€ 500.000 k.k.</div>
    </body></html>
    """
    scraper = static_pararius_scraper(minimal_html)
    detail = scraper.scrape_detail("https://www.pararius.nl/huis-te-koop/any/")

    assert detail.price == "€ 500.000 k.k."
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 is None
    assert detail.room_count is None
    assert detail.bedroom_count is None
    assert detail.bathroom_count is None
    assert detail.construction_period is None
    assert detail.energy_label is None
    assert detail.postcode is None
