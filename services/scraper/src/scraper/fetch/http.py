import httpx
from loguru import logger


class HttpFetch:
    def __init__(self, timeout: float = 30.0) -> None:
        self.client = httpx.Client(timeout=timeout)

    def fetch(self, url: str) -> str:
        logger.debug(f"HTTP fetch: {url}")
        response = self.client.get(url)
        response.raise_for_status()
        return response.text

    def close(self) -> None:
        self.client.close()
