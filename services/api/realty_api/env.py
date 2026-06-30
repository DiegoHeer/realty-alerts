from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    realty_api_key: str = Field(...)
    bag_api_key: str = Field(...)
    ep_online_api_key: str = Field(...)
    django_secret_key: str | None = None
    allowed_hosts: str = ""
    csrf_trusted_origins: str = ""
    cors_allowed_origins: str = ""
    log_level: str = "INFO"
    timezone: str = "Europe/Amsterdam"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = False
    argo_events_webhook_url: str | None = None
    dso_api_key: str | None = None
    headless_jwt_private_key: str | None = None

    # Email / SMTP. Defaults suit local dev (console backend); prod.py switches
    # to SMTP and validates the host/credentials are real.
    email_backend: str = "django.core.mail.backends.console.EmailBackend"
    email_host: str = "localhost"
    email_port: int = 25
    email_host_user: str = ""
    email_host_password: str = ""
    email_use_tls: bool = False
    email_use_ssl: bool = False
    default_from_email: str = "Realty Alerts <noreply@realty-alerts.app>"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cache_url(self) -> str | None:
        """Redis URL for the Django cache, derived from the Celery broker by
        switching to logical DB 1 (broker uses DB 0). Reuses the broker's host
        and credentials so no separate secret is needed. Returns None when the
        broker isn't Redis (e.g. preview namespaces use ``memory://``), letting
        settings fall back to a local-memory cache."""
        parts = urlsplit(self.celery_broker_url)
        if parts.scheme not in ("redis", "rediss"):
            return None
        return urlunsplit(parts._replace(path="/1"))


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
