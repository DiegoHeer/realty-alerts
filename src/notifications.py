import backoff
import requests
from loguru import logger
from requests.exceptions import ConnectionError, RequestException

from models import QueryResult, RealtyQuery


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
        "Title": f"{query_result.query_name} -> {query_result.title}",
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
        message = f"Query scheduling for {query.name} is successfully enabled"
        logger.info(message)

        if not query.notify_startup_of_app:
            logger.info(f"Not sending startup notification message of query '{query.name}' to topic {query.ntfy_topic}")
            continue

        headers = {
            "Priority": "min",
            "Tags": "partying_face, heavy_check_mark",
            "Title": f"{query.name} -> Scheduling started",
        }
        _send_to_ntfy(query.notification_url, headers, message)
