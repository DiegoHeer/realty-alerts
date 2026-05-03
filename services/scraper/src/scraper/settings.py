from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Job-specific
    website: str = Field(...)

    # Infrastructure
    backend_api_url: str = "http://localhost:8000"
    # WebSocket URL of a remote Playwright server (e.g. browserless). The scraper image does not bundle browsers.
    browser_url: str = "ws://localhost:3000"
    realty_api_key: str = Field(...)

    # Operational
    timezone: str = "Europe/Amsterdam"
    log_level: str = "INFO"
