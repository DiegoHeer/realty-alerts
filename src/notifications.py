import logging

import requests

from models import QueryResult
from settings import SETTINGS

LOGGER = logging.getLogger(__name__)


def send_notifications(result_queries: list[QueryResult]) -> None:
    for result_query in result_queries:
        headers = _build_headers(result_query)
        message = _build_message(result_query)
        _send_to_ntfy(headers, message)

    if not result_queries:
        LOGGER.info("No new notifications available")


def _build_message(result_query: QueryResult) -> str:
    return f"Price: {result_query.price}"


# NTFY messaging options: https://docs.ntfy.sh/publish
def _build_headers(result_query: QueryResult) -> dict[str, str]:
    return {
        "Priority": "urgent",
        "Tags": "house, rotating_light",
        "Title": f"New house for sale: {result_query.title}",
        "Click": result_query.detail_url,
        "Attach": result_query.image_url,
    }


def _send_to_ntfy(headers: dict, message: str) -> None:
    response = requests.post(SETTINGS.ntfy_url, data=message.encode(), headers=headers)

    if response.ok:
        LOGGER.info(f"Notification '{message}' has been successfully send to {SETTINGS.ntfy_url}")
    else:
        LOGGER.error(
            f"Failed to send notification '{message}' to {SETTINGS.ntfy_url}. Status code: {response.status_code}"
        )
