from datetime import datetime

import httpx

from scraper.models import Listing


class BackendClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )

    def get_last_successful_run(self, website: str) -> datetime | None:
        raise NotImplementedError

    def submit_results(self, website: str, listings: list[Listing]) -> None:
        raise NotImplementedError

    def health_check(self) -> bool:
        raise NotImplementedError
