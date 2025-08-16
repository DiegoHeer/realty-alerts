import backoff
import requests
from loguru import logger
from requests.exceptions import ConnectionError, RequestException

from models import QueryResult


def notify_about_new_results(url: str, query_results: list[QueryResult]) -> None:
    for result_query in query_results:
        headers = _build_headers(result_query)
        message = _build_message(result_query)
        _send_to_ntfy(url, headers, message)

    if not query_results:
        logger.info("No new notifications available")


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
