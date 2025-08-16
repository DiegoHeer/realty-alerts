import backoff
import requests
from loguru import logger
from requests.exceptions import ConnectionError, RequestException

from models import QueryResult


def notify_about_new_results(query_name: str, url: str, query_results: list[QueryResult]) -> list[QueryResult]:
    query_results = _limit_max_amount_of_notifications(query_results)

    for result_query in query_results:
        headers = _build_headers(result_query)
        message = _build_message(result_query)
        _send_to_ntfy(url, headers, message)

    if not query_results:
        logger.info(f"No new notifications available for query: {query_name}")

    return query_results


def _limit_max_amount_of_notifications(query_results: list[QueryResult]) -> list[QueryResult]:
    """THis is to avoid 429 status code errors when sending too many notifications in one go"""
    MAX_AMOUNT_OF_NOTIFICATIONS = 50

    return query_results[:MAX_AMOUNT_OF_NOTIFICATIONS]


def _build_message(query_result: QueryResult) -> str:
    return f"New house for sale. Price: {query_result.price}"


# NTFY messaging options: https://docs.ntfy.sh/publish
def _build_headers(query_result: QueryResult) -> dict[str, str]:
    return {
        "Priority": "urgent",
        "Tags": "house, rotating_light",
        "Title": f"{query_result.title}",
        "Click": query_result.detail_url,
        "Attach": query_result.image_url,
    }


@backoff.on_exception(backoff.expo, (ConnectionError, RequestException), max_tries=3)
def _send_to_ntfy(url: str, headers: dict, message: str) -> None:
    response = requests.post(url, data=message.encode(), headers=headers)

    if response.ok:
        logger.info(f"Notification '{headers['Title']}' has been successfully send to {url}")
    else:
        logger.error(f"Failed to send notification '{message}' to {url}. Status code: {response.status_code}")
        response.raise_for_status()
