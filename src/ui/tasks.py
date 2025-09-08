from celery import shared_task
from django.core import serializers
from playwright.sync_api import sync_playwright

from enums import QueryResultStatus
from models import QueryResult
from notifications import notify_about_new_results
from scraper.scrape_selector import get_scraper_class
from ui.models import RealtyQuery, RealtyResult


@shared_task
def scrape_and_notify(query_name: str) -> None:
    """Scrapes house listings based on query, and sends notifications about new results."""

    realty_query = RealtyQuery.objects.get(name=query_name)
    query_results = _scrape_query(realty_query)
    _save_query_results(realty_query, query_results)

    new_query_results = _get_new_query_results(query_name=realty_query.name)
    notified_query_results = notify_about_new_results(
        query_name=realty_query.name, url=realty_query.notification_url, query_results=new_query_results
    )

    _update_query_results_status(realty_query.name, notified_query_results, status=QueryResultStatus.NOTIFIED)


def _scrape_query(realty_query: RealtyQuery) -> list[QueryResult]:
    scraper_class = get_scraper_class(website=realty_query.website)
    with sync_playwright() as playwright:
        scraper = scraper_class(
            playwright,
            query_url=realty_query.query_url,
            max_listing_page_number=realty_query.max_listing_page_number,
        )
        return scraper.get_query_results()


def _save_query_results(realty_query: RealtyQuery, query_results: list[QueryResult]) -> None:
    for query_result in query_results:
        record, created = RealtyResult.objects.get_or_create(
            query=realty_query,
            detail_url=query_result.detail_url,
            defaults=_get_query_result_defaults(query_result),
        )

        if not created and not _is_record_archived(record) and _is_query_result_changed(query_result, record):
            _update_record_from_query_result(record, query_result)


def _get_query_result_defaults(query_result: QueryResult) -> dict:
    return {
        "title": query_result.title,
        "price": query_result.price,
        "image_url": query_result.image_url,
    }


def _is_query_result_changed(query_result: QueryResult, record: RealtyResult) -> bool:
    return any(
        getattr(record, field) != getattr(query_result, field)
        for field in query_result.__class__.model_fields
        if hasattr(record, field)
    )


def _is_record_archived(record: RealtyResult) -> bool:
    return record.status == QueryResultStatus.ARCHIVED


def _update_record_from_query_result(record: RealtyResult, query_result: QueryResult) -> None:
    for key, value in query_result.model_dump().items():
        if hasattr(record, key):
            setattr(record, key, value)

    record.status = QueryResultStatus.UPDATED
    record.save()


def _get_new_query_results(query_name: str) -> list[QueryResult]:
    db_records = RealtyResult.objects.filter(query__name=query_name, status=QueryResultStatus.NEW)
    dict_records = serializers.serialize("python", db_records)

    return [QueryResult.model_validate(record["fields"]) for record in dict_records]


def _update_query_results_status(query_name: str, query_results: list[QueryResult], status: QueryResultStatus) -> None:
    detail_urls = [result.detail_url for result in query_results]
    db_records = RealtyResult.objects.filter(query__name=query_name, detail_url__in=detail_urls)
    db_records.update(status=status)
