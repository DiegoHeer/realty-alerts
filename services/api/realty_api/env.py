from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    internal_api_key: str = Field(...)
    django_secret_key: str | None = None
    log_level: str = "INFO"
    timezone: str = "Europe/Amsterdam"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
