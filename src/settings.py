from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ntfy_url: str = "https://ntfy.sh/realty-alerts"
    redis_url: str = "redis://localhost:6379/0"
    timezone: str = "Europe/Amsterdam"


SETTINGS = Settings()
DATA_PATH = Path(__file__).resolve().parents[1] / "data"
