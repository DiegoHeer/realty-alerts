from core.settings.base import *  # noqa: F403, F401
import dj_database_url

DEBUG = False
ALLOWED_HOSTS = ["*"]

# HTTPS / SSL Settings
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# Static files
STATIC_ROOT = "/tmp/staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Databases
DATABASES = {"default": dj_database_url.config(conn_max_age=600, conn_health_checks=True)}

# Tailwind/CSS
TAILWIND_CLI_VERSION = "4.1.12"
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = False
TAILWIND_CLI_DIST_CSS = "css/tailwind.min.css"
