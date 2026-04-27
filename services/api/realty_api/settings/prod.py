from typing import cast

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from realty_api.env import SETTINGS
from realty_api.settings.base import *  # noqa: F403, F401

if not SETTINGS.django_secret_key:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY is required in production.")

SECRET_KEY = SETTINGS.django_secret_key

DEBUG = False

ALLOWED_HOSTS = [h.strip() for h in SETTINGS.allowed_hosts.split(",") if h.strip()]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set (comma-separated) in production.")

CSRF_TRUSTED_ORIGINS = [o.strip() for o in SETTINGS.csrf_trusted_origins.split(",") if o.strip()]
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured("CSRF_TRUSTED_ORIGINS must be set (comma-separated, scheme included) in production.")

if not SETTINGS.celery_broker_url or SETTINGS.celery_broker_url.startswith("redis://localhost"):
    raise ImproperlyConfigured(
        "CELERY_BROKER_URL must be set to a non-localhost redis URL in production.",
    )
if not SETTINGS.celery_result_backend or SETTINGS.celery_result_backend.startswith("redis://localhost"):
    raise ImproperlyConfigured(
        "CELERY_RESULT_BACKEND must be set to a non-localhost redis URL in production.",
    )

# HTTPS / SSL
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Static files
STATIC_ROOT = "/tmp/staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Database (DATABASE_URL required)
DATABASES = {"default": cast(dict, dj_database_url.config(conn_max_age=600, conn_health_checks=True))}
