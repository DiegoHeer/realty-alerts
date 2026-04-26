import os

# Sensible defaults for local dev / test runs. Production must set these explicitly via prod.py.
os.environ.setdefault("INTERNAL_API_KEY", "dev-internal-api-key")

from secret_key_generator import secret_key_generator  # noqa: E402

from realty_api.settings.base import *  # noqa: E402, F403, F401

DEBUG = True

# Single-process runserver; per-boot regeneration is harmless and avoids requiring an env var locally.
SECRET_KEY = secret_key_generator.generate()
