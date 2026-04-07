import httpx
from loguru import logger


class HttpFetch:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> str:
        logger.debug(f"HTTP fetch: {url}")
        response = httpx.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text
