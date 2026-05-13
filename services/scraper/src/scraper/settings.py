from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from scraper.enums import ScrapeMode


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Job-specific
    website: str = Field(...)
    scrape_mode: ScrapeMode = ScrapeMode.LIST
    detail_url: str | None = None
    listing_id: int | None = None

    # Infrastructure
    backend_api_url: str = "http://localhost:8000"
    # WebSocket URL of a remote Playwright server (e.g. browserless). The scraper image does not bundle browsers.
    browser_url: str = "ws://localhost:3000"
    realty_api_key: str = Field(...)

    # Operational
    timezone: str = "Europe/Amsterdam"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _validate_detail_mode(self) -> Self:
        if self.scrape_mode == ScrapeMode.DETAIL:
            if self.detail_url is None:
                raise ValueError("detail_url is required when scrape_mode is 'detail'")
            if self.listing_id is None:
                raise ValueError("listing_id is required when scrape_mode is 'detail'")
        return self
