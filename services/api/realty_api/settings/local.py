import os

# Sensible defaults for local dev / test runs. Production must set these explicitly via prod.py.
os.environ.setdefault("REALTY_API_KEY", "dev-realty-api-key")

from secret_key_generator import secret_key_generator  # noqa: E402

from realty_api.settings.base import *  # noqa: E402, F403, F401

DEBUG = True

# Single-process runserver; per-boot regeneration is harmless and avoids requiring an env var locally.
SECRET_KEY = secret_key_generator.generate()

# Use DATABASE_URL when running inside Docker; fall back to SQLite for plain `manage.py runserver`.
if _db_url := os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": dj_database_url.parse(_db_url, conn_max_age=60)}

# collectstatic needs a writable target even in dev-container mode.
STATIC_ROOT = "/tmp/staticfiles"
