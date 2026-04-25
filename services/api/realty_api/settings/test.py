"""Settings for CI test runs against a real Postgres service."""

import dj_database_url

from realty_api.settings.base import *  # noqa: F403, F401

DATABASES = {"default": dj_database_url.config()}
