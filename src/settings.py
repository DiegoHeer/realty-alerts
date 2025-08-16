from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ntfy_url: str = "https://ntfy.sh"
    redis_url: str = "redis://localhost:6379/0"
    browser_url: str = "ws://localhost:3000"
    timezone: str = "Europe/Amsterdam"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
