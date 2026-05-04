from datetime import datetime

import httpx
from loguru import logger

from scraper.models import DeadListing, Listing


class BackendClient:
    def __init__(self, base_url: str, api_key: str) -> None:
        self.client = httpx.Client(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=30.0,
        )

    def health_check(self) -> bool:
        try:
            response = self.client.get("/healthz")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def get_last_successful_run(self, website: str) -> datetime | None:
        response = self.client.get(f"/internal/v1/scrape-runs/{website}/last-successful")
        response.raise_for_status()
        data = response.json()
        if data is None:
            return None
        return datetime.fromisoformat(data["started_at"])

    def submit_results(
        self,
        website: str,
        listings: list[Listing],
        dead_listings: list[DeadListing],
        started_at: datetime,
        finished_at: datetime,
        error_message: str | None = None,
    ) -> dict:
        payload = {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "error_message": error_message,
            "listings": [listing.model_dump() for listing in listings],
            "dead_listings": [dead.model_dump() for dead in dead_listings],
        }
        response = self.client.post(f"/internal/v1/scrape-runs/{website}/results", json=payload)
        response.raise_for_status()
        result = response.json()
        logger.info(
            f"Submitted {result['listings_found']} listings "
            f"({result['new_residences_count']} new residences, "
            f"{result['new_listings_count']} new listings) "
            f"and {len(dead_listings)} dead for {website}"
        )
        return result
