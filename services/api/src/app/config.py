from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="API_", env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://localhost:5432/realty_alerts"

    # Supabase Auth
    supabase_url: str = ""
    supabase_jwt_secret: str = ""

    # Internal API
    internal_api_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    timezone: str = "Europe/Amsterdam"

    # CORS
    cors_origins: list[str] = ["*"]
