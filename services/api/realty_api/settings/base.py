"""
Django settings for realty_api project.

Shared between local and prod. Per-environment overrides live in
``realty_api/settings/local.py`` and ``realty_api/settings/prod.py``.
"""

from pathlib import Path

from realty_api.env import SETTINGS

BASE_DIR = Path(__file__).resolve().parents[2]

# SECRET_KEY is intentionally not set here. Each environment (local/ci/prod) sets it.

ALLOWED_HOSTS: list[str] = []

REALTY_API_KEY = SETTINGS.realty_api_key
BAG_API_KEY = SETTINGS.bag_api_key
EP_ONLINE_API_KEY = SETTINGS.ep_online_api_key
DSO_API_KEY = SETTINGS.dso_api_key

# API contract versioning (see scraping/middleware.py and GET /v1/meta).
API_CURRENT_VERSION = 2
API_MIN_SUPPORTED_VERSION = 1
# Maps an api_version integer to its RFC 8594 lifecycle headers. Empty until a
# contract is actually deprecated; the middleware emits no headers when absent.
API_VERSION_LIFECYCLE: dict[int, dict[str, str]] = {}

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "scraping",
    "django_celery_beat",
    "django_celery_results",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "scraping.middleware.ApiVersioningMiddleware",
]

ROOT_URLCONF = "realty_api.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "realty_api.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".local.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = SETTINGS.timezone
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Celery ---
CELERY_BROKER_URL = SETTINGS.celery_broker_url
CELERY_RESULT_BACKEND = "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_TIMEZONE = SETTINGS.timezone
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 240
CELERY_TASK_ALWAYS_EAGER = SETTINGS.celery_task_always_eager
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# --- Argo Events bridge ---
# The webhook URL the `scraping.dispatch_list_scrape` Celery task POSTs to
# in order to spawn a scrape Job via Argo Events. Empty/None lets the
# task short-circuit (logged warning, no HTTP call) — useful in local
# dev and preview namespaces that don't run Argo Events.
ARGO_EVENTS_WEBHOOK_URL = SETTINGS.argo_events_webhook_url

# --- django-allauth (headless) ---
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("app",)

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True

# Collect a required display name at signup, persisted to User.first_name.
ACCOUNT_SIGNUP_FORM_CLASS = "scraping.forms.SignupForm"
# Expose that name on the serialized headless user object (login/session).
HEADLESS_ADAPTER = "scraping.adapters.HeadlessAdapter"

HEADLESS_TOKEN_STRATEGY = "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy"
HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = 1800  # 30 minutes
HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = 31_536_000  # 365 days (inactivity window; rotation is on)
HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True

# --- Email ---
# Backend defaults to console (dev/test). prod.py forces the SMTP backend and
# validates the host/credentials; local dev can opt into SMTP by setting
# EMAIL_BACKEND + the EMAIL_* vars in .env. All values come from the environment.
EMAIL_BACKEND = SETTINGS.email_backend
EMAIL_HOST = SETTINGS.email_host
EMAIL_PORT = SETTINGS.email_port
EMAIL_HOST_USER = SETTINGS.email_host_user
EMAIL_HOST_PASSWORD = SETTINGS.email_host_password
EMAIL_USE_TLS = SETTINGS.email_use_tls
EMAIL_USE_SSL = SETTINGS.email_use_ssl
DEFAULT_FROM_EMAIL = SETTINGS.default_from_email
