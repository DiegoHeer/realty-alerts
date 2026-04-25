import os

# Sensible defaults for local dev / test runs. Production must set these explicitly via prod.py.
os.environ.setdefault("INTERNAL_API_KEY", "dev-internal-api-key")

from realty_api.settings.base import *  # noqa: E402, F403, F401

DEBUG = True
