import pytest
from pytest_mock import MockerFixture

from enums import QueryResultStatus
from scraper.base import BaseScraper
from tests.scraper.conftest import mock_scrape_url_content
from ui.models import RealtyResult
from ui.tasks import scrape_and_notify
from ui.tests.factories import RealtyQueryFactory, RealtyResultFactory


@pytest.fixture
def realty_query(db):
    return RealtyQueryFactory(
        query_url="https://aanbod.vastgoednederland.nl/koopwoningen?q=den+haag",
        max_listing_page_number=1,
    )


@pytest.fixture
def realty_result(db, realty_query):
    return [
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576379-gentsestraat-77",
        )
    ]


@pytest.fixture
def realty_results(db, realty_query):
    return [
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576491-smaragdhorst-100",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576469-gerard-kellerstraat-21",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576457-helmersstraat-26",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576393-schoolmeesterstraat-11",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576389-louis-davidsstraat-361",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576385-burgemeester-patijnlaan-712",
        ),
        RealtyResultFactory(
            query=realty_query,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576380-ijmuidenstraat-39",
        ),
        RealtyResultFactory(
            query=realty_query,
            status=QueryResultStatus.ARCHIVED,
            detail_url="https://aanbod.vastgoednederland.nl/koopwoningen/s-gravenhage/woning-576380-ijmuidenstraat-40",
        ),
    ]


def test_scrape_and_notify__success(mocker: MockerFixture, realty_query):
    mocker.patch.object(BaseScraper, "_connect_browser")
    mocker.patch.object(BaseScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))

    scrape_and_notify(query_name=realty_query.name)

    assert RealtyResult.objects.count() == 8
    assert RealtyResult.objects.filter(status=QueryResultStatus.NOTIFIED).count() == 8
    assert mock_post.call_count == 8


def test_scrape_and_notify__one_new_result(mocker: MockerFixture, realty_query, realty_results):
    mocker.patch.object(BaseScraper, "_connect_browser")
    mocker.patch.object(BaseScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))

    scrape_and_notify(query_name=realty_query.name)

    assert RealtyResult.objects.count() == 8
    assert RealtyResult.all_objects.count() == 9
    assert RealtyResult.objects.filter(status=QueryResultStatus.NOTIFIED).count() == 1
    assert RealtyResult.objects.filter(status=QueryResultStatus.UPDATED).count() == 7
    assert RealtyResult.objects.filter(status=QueryResultStatus.ARCHIVED).count() == 0
    assert RealtyResult.all_objects.filter(status=QueryResultStatus.ARCHIVED).count() == 1
    assert mock_post.call_count == 1


def test_scrape_and_notify__no_new_results(mocker: MockerFixture, realty_query, realty_result, realty_results):
    mocker.patch.object(BaseScraper, "_connect_browser")
    mocker.patch.object(BaseScraper, "_scrape_url_content", side_effect=mock_scrape_url_content)
    mock_post = mocker.patch("notifications.requests.post", return_value=mocker.MagicMock(ok=True))

    scrape_and_notify(query_name=realty_query.name)

    assert RealtyResult.objects.count() == 8
    assert RealtyResult.objects.filter(status=QueryResultStatus.NOTIFIED).count() == 0
    assert RealtyResult.objects.filter(status=QueryResultStatus.UPDATED).count() == 8
    assert mock_post.call_count == 0
