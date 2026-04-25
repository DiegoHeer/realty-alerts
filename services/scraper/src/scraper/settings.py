from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Job-specific
    website: str
    scrape_scope: str = "all"

    # Infrastructure
    backend_api_url: str = "http://localhost:8000"
    browser_url: str = "ws://localhost:3000"
    scraper_api_key: str

    # Operational
    timezone: str = "Europe/Amsterdam"
    log_level: str = "INFO"
