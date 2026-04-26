"""Settings for CI test runs against a real Postgres service."""

from typing import cast

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from realty_api.env import SETTINGS
from realty_api.settings.base import *  # noqa: F403, F401

if not SETTINGS.django_secret_key:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in CI.")

SECRET_KEY = SETTINGS.django_secret_key

DATABASES = {"default": cast(dict, dj_database_url.config())}
