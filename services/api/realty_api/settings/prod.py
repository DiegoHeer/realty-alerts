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

if not SETTINGS.argo_events_webhook_url:
    raise ImproperlyConfigured(
        "ARGO_EVENTS_WEBHOOK_URL must be set in production "
        "(e.g. http://scrape-webhook-eventsource-svc.<ns>.svc.cluster.local:12000/scrape).",
    )

# HTTPS / SSL
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Client IP for allauth rate limiting. The request path is
# Cloudflare -> cloudflared -> Traefik -> pod, and Traefik rewrites
# X-Forwarded-For / X-Real-IP to the in-cluster peer. The only trustworthy
# client IP is Cloudflare's CF-Connecting-IP, set at the edge and not
# spoofable by clients. allauth distrusts X-Forwarded-For by default.
ALLAUTH_TRUSTED_CLIENT_IP_HEADER = "CF-Connecting-IP"

# Static files
STATIC_ROOT = "/tmp/staticfiles"
STORAGES = {
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# Database (DATABASE_URL required)
DATABASES = {"default": cast(dict, dj_database_url.config(conn_max_age=600, conn_health_checks=True))}

# JWT signing key (PEM-encoded RSA private key)
if not SETTINGS.headless_jwt_private_key:
    raise ImproperlyConfigured("HEADLESS_JWT_PRIVATE_KEY must be set in production (PEM-encoded RSA private key).")

HEADLESS_JWT_PRIVATE_KEY = SETTINGS.headless_jwt_private_key

# Google OAuth (Web client id/secret used to verify Google id tokens).
if not SETTINGS.google_oauth_client_id or not SETTINGS.google_oauth_client_secret:
    raise ImproperlyConfigured(
        "GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET must be set in production "
        "(the Web OAuth client id/secret used to verify Google id tokens)."
    )

# Email (SMTP) — transactional auth mail: verification codes, password reset.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
if not SETTINGS.email_host or SETTINGS.email_host == "localhost":
    raise ImproperlyConfigured("EMAIL_HOST must be set to a real SMTP host in production.")
if not SETTINGS.email_host_user or not SETTINGS.email_host_password:
    raise ImproperlyConfigured(
        "EMAIL_HOST_USER and EMAIL_HOST_PASSWORD must be set in production for transactional email.",
    )
