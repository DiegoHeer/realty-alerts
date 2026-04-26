from typing import cast

import dj_database_url

from realty_api.settings.base import *  # noqa: F403, F401

DEBUG = False
ALLOWED_HOSTS = ["*"]

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
