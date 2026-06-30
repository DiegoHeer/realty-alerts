"""Settings for CI test runs against a real Postgres service."""

from typing import cast

import dj_database_url
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from django.core.exceptions import ImproperlyConfigured

from realty_api.env import SETTINGS
from realty_api.settings.base import *  # noqa: F403, F401

if not SETTINGS.django_secret_key:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in CI.")

SECRET_KEY = SETTINGS.django_secret_key

DATABASES = {"default": cast(dict, dj_database_url.config())}

_ci_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
HEADLESS_JWT_PRIVATE_KEY = _ci_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CI serves no browsers; don't police CORS here. Tests that exercise the
# controlled prod policy pin it explicitly via override_settings.
CORS_ALLOW_ALL_ORIGINS = True
