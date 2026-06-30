import os
from typing import cast

# Sensible defaults for local dev / test runs. Production must set these explicitly via prod.py.
os.environ.setdefault("REALTY_API_KEY", "dev-realty-api-key")
os.environ.setdefault("BAG_API_KEY", "dev-bag-api-key")
os.environ.setdefault("EP_ONLINE_API_KEY", "dev-ep-online-api-key")
os.environ.setdefault("DSO_API_KEY", "dev-dso-api-key")

from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat  # noqa: E402
from secret_key_generator import secret_key_generator  # noqa: E402

from realty_api.settings.base import *  # noqa: E402, F403, F401

DEBUG = True

# Single-process runserver; per-boot regeneration is harmless and avoids requiring an env var locally.
SECRET_KEY = secret_key_generator.generate()

_dev_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
HEADLESS_JWT_PRIVATE_KEY = _dev_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()

# EMAIL_BACKEND comes from base.py (SETTINGS.email_backend) and defaults to the
# console backend. To exercise real SMTP delivery locally, set EMAIL_BACKEND and
# the EMAIL_* vars in .env (e.g. django.core.mail.backends.smtp.EmailBackend).

# Use DATABASE_URL when running inside Docker; fall back to SQLite for plain `manage.py runserver`.
if _db_url := os.environ.get("DATABASE_URL"):
    import dj_database_url

    DATABASES = {"default": cast(dict, dj_database_url.parse(_db_url, conn_max_age=60))}

# collectstatic needs a writable target even in dev-container mode.
STATIC_ROOT = "/tmp/staticfiles"

# Single-process dev (runserver) doesn't need a shared cache for rate-limit
# counters; use LocMemCache so plain `runserver` has no hard Redis dependency.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# CORS: wide open in local dev so any browser origin (web build on any port,
# LAN device, tunnel) just works without configuring CORS_ALLOWED_ORIGINS.
# Safe because credentials are off (JWT travels in the Authorization header,
# not cookies). The controlled, env-driven policy lives in base.py for prod.
CORS_ALLOW_ALL_ORIGINS = True
