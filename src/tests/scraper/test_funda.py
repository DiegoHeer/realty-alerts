import pytest

from enums import EnergyLabel, HouseTypes
from models import QueryFilter
from scraper.funda import FundaScraper


@pytest.fixture
def house_type_query_filter() -> QueryFilter:
    return QueryFilter(house_types=[HouseTypes.WOONHUIS, HouseTypes.APPARTEMENT])


@pytest.fixture
def energy_label_query_filter() -> QueryFilter:
    return QueryFilter(energy_labels=[EnergyLabel.A_TWO_PLUS, EnergyLabel.A_PLUS, EnergyLabel.G])


@pytest.fixture
def price_range_query_filter() -> QueryFilter:
    return QueryFilter(max_price=310000)


@pytest.fixture
def floor_area_query_filter() -> QueryFilter:
    return QueryFilter(min_floor_area=60)


@pytest.fixture
def rooms_query_filter() -> QueryFilter:
    return QueryFilter(min_rooms=2, max_rooms=5)


@pytest.fixture
def bedrooms_query_filter() -> QueryFilter:
    return QueryFilter(min_bedrooms=2, max_bedrooms=5)


@pytest.fixture
def funda_scraper(house_type_query_filter) -> FundaScraper:
    return FundaScraper(house_type_query_filter)


def test_build_query_url__house_types(house_type_query_filter):
    query_url = FundaScraper(house_type_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?object_type=%5B%22apartment%22%2C%20%22house%22%5D"


def test_build_query_url__energy_labels(energy_label_query_filter):
    query_url = FundaScraper(energy_label_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?energy_label=%5B%22A%2B%22%2C%20%22A%2B%2B%22%2C%20%22G%22%5D"


def test_build_query_url__price_range(price_range_query_filter):
    query_url = FundaScraper(price_range_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?price=%22-310000%22"


def test_build_query_url__floor_area(floor_area_query_filter):
    query_url = FundaScraper(floor_area_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?floor_area=%2260-%22"


def test_build_query_url__rooms(rooms_query_filter):
    query_url = FundaScraper(rooms_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?rooms=%222-5%22"


def test_build_query_url__bedrooms(bedrooms_query_filter):
    query_url = FundaScraper(bedrooms_query_filter).build_query_url()

    assert query_url == "https://www.funda.nl/zoeken/koop?bedrooms=%222-5%22"
