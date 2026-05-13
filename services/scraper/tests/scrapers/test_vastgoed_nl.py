from scraper.enums import ListingStatus
from scraper.models import DetailListing

DETAIL_URL = "https://aanbod.vastgoednederland.nl/koopwoningen/well-l/woning-636480-wolfsven-11"


def test_scrape_detail_returns_detail_listing(vastgoed_nl_scraper):
    detail = vastgoed_nl_scraper.scrape_detail(DETAIL_URL)

    assert isinstance(detail, DetailListing)
    assert detail.price == "€ 510.000,- k.k."
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 == 95
    assert detail.room_count == 3
    assert detail.bedroom_count == 2
    assert detail.bathroom_count == 1
    assert detail.construction_period == "1991-2000"
    assert detail.energy_label == "A"
    assert detail.postcode == "5855ER"


def test_scrape_detail_returns_none_for_absent_fields(static_vastgoed_nl_scraper):
    minimal_html = """
    <html><body>
    <span class="price">€ 250.000,- k.k.</span>
    <span class="info-badge primary">beschikbaar</span>
    </body></html>
    """
    scraper = static_vastgoed_nl_scraper(minimal_html)
    detail = scraper.scrape_detail("https://example.com/listing")

    assert detail.price == "€ 250.000,- k.k."
    assert detail.status == ListingStatus.NEW
    assert detail.surface_area_m2 is None
    assert detail.bedroom_count is None
    assert detail.bathroom_count is None
    assert detail.room_count is None
    assert detail.construction_period is None
    assert detail.energy_label is None
    assert detail.postcode is None


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
