from core.settings.base import *  # noqa: F403, F401
from core.settings.base import DATA_DIR

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
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "prod.sqlite3",
    }
}
