import logging

import requests

from models import QueryResult, RealtyQuery
from settings import SETTINGS

LOGGER = logging.getLogger(__name__)


def notify_about_new_results(url: str, query_results: list[QueryResult]) -> None:
    for result_query in query_results:
        headers = _build_headers(result_query)
        message = _build_message(result_query)
        _send_to_ntfy(url, headers, message)

    if not query_results:
        LOGGER.info("No new notifications available")


def _build_message(query_result: QueryResult) -> str:
    return f"New house for sale. Price: {query_result.price}"


# NTFY messaging options: https://docs.ntfy.sh/publish
def _build_headers(query_result: QueryResult) -> dict[str, str]:
    return {
        "Priority": "urgent",
        "Tags": "house, rotating_light",
        "Title": f"{query_result.query_name} -> {query_result.title}",
        "Click": query_result.detail_url,
        "Attach": query_result.image_url,
    }


def _send_to_ntfy(url: str, headers: dict, message: str) -> None:
    response = requests.post(url, data=message.encode(), headers=headers)

    if response.ok:
        LOGGER.info(f"Notification '{headers['Title']}' has been successfully send to {SETTINGS.ntfy_url}")
    else:
        LOGGER.error(
            f"Failed to send notification '{message}' to {SETTINGS.ntfy_url}. Status code: {response.status_code}"
        )
        response.raise_for_status()


def notify_when_there_are_no_new_listings(query: RealtyQuery) -> None:
    headers = {
        "Priority": "min",
        "Tags": "no_entry_sign",
        "Title": f"{query.name} -> No new house listings",
        "Click": query.query_url,
    }
    message = f"There are no new house listings for your query on {query.website}"
    _send_to_ntfy(query.notification_url, headers, message)


def notify_about_successful_startup(queries: list[RealtyQuery]) -> None:
    for query in queries:
        headers = {
            "Priority": "min",
            "Tags": "partying_face, heavy_check_mark",
            "Title": f"{query.name} -> Scheduling started",
        }
        message = f"Query scheduling for {query.name} is successfully enabled"
        _send_to_ntfy(query.notification_url, headers, message)
