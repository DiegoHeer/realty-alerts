from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    realty_api_key: str = Field(...)
    bag_api_key: str = Field(...)
    django_secret_key: str | None = None
    allowed_hosts: str = ""
    csrf_trusted_origins: str = ""
    log_level: str = "INFO"
    timezone: str = "Europe/Amsterdam"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False
    argo_events_webhook_url: str | None = None

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
