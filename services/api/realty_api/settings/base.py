"""
Django settings for realty_api project.

Shared between local and prod. Per-environment overrides live in
``realty_api/settings/local.py`` and ``realty_api/settings/prod.py``.
"""

from pathlib import Path

from corsheaders.defaults import default_headers

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
API_MIN_SUPPORTED_VERSION = 2
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
    "django.contrib.sites",
    "django.contrib.postgres",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "scraping",
    "accounts",
    "django_celery_beat",
    "django_celery_results",
]

MIDDLEWARE = [
    # CorsMiddleware must sit above anything that can generate a response
    # (WhiteNoise, CommonMiddleware) so preflight replies carry CORS headers.
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "scraping.middleware.ApiVersioningMiddleware",
]

ROOT_URLCONF = "realty_api.urls"
SITE_ID = 1

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
                "scraping.context_processors.email_branding",
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
LANGUAGES = [
    ("en", "English"),
    ("nl", "Nederlands"),
    ("pt", "Português"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
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


# --- Cache ---
# allauth's rate limiter keys on CACHES["default"]; it must be a shared backend
# (Redis) or per-process LocMemCache lets limits multiply by worker/pod count.
# The Redis URL is derived from the Celery broker (DB 1); when the broker isn't
# Redis (preview namespaces use memory://) we fall back to LocMemCache. local.py
# and ci.py override this to LocMemCache (no Redis dependency, single process).
def _cache_config(cache_url: str | None) -> dict:
    if cache_url:
        backend = {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": cache_url}
    else:
        backend = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    return {"default": backend}


CACHES = _cache_config(SETTINGS.cache_url)

# --- Django Ninja throttling ---
# Per-user write buckets for authenticated /v1/me endpoints. UserWriteThrottle
# and UserMergeThrottle read their rate from here by scope. Feedback throttling
# hardcodes its own rates on FeedbackThrottle and is intentionally not listed.
NINJA_DEFAULT_THROTTLE_RATES = {
    "user_write": "60/min",
    "user_merge": "10/min",
}

# --- Argo Events bridge ---
# The webhook URL the `scraping.dispatch_list_scrape` Celery task POSTs to
# in order to spawn a scrape Job via Argo Events. Empty/None lets the
# task short-circuit (logged warning, no HTTP call) — useful in local
# dev and preview namespaces that don't run Argo Events.
ARGO_EVENTS_WEBHOOK_URL = SETTINGS.argo_events_webhook_url

# Mattermost incoming-webhook URL for the feedback channel. Unset ⇒ the
# notification task short-circuits (logged warning, no HTTP call); feedback is
# still stored. Best-effort, so it stays optional in every environment.
MATTERMOST_FEEDBACK_WEBHOOK_URL = SETTINGS.mattermost_feedback_webhook_url

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
# Security-notice emails (password/email changed, email deleted) are only sent
# when this is True; allauth's send_notification_mail() early-returns otherwise.
ACCOUNT_EMAIL_NOTIFICATIONS = True
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_ENABLED = True
ACCOUNT_PASSWORD_RESET_BY_CODE_TIMEOUT = 15 * 60

# Collect a required display name at signup, persisted to User.first_name.
ACCOUNT_SIGNUP_FORM_CLASS = "scraping.forms.SignupForm"
# Adds a monitored Reply-To (settings.EMAIL_REPLY_TO) to transactional auth mail.
ACCOUNT_ADAPTER = "scraping.adapters.AccountAdapter"
# Expose that name on the serialized headless user object (login/session).
HEADLESS_ADAPTER = "scraping.adapters.HeadlessAdapter"

HEADLESS_TOKEN_STRATEGY = "allauth.headless.tokens.strategies.jwt.JWTTokenStrategy"
HEADLESS_JWT_ACCESS_TOKEN_EXPIRES_IN = 1800  # 30 minutes
HEADLESS_JWT_REFRESH_TOKEN_EXPIRES_IN = 31_536_000  # 365 days (inactivity window; rotation is on)
HEADLESS_JWT_ROTATE_REFRESH_TOKEN = True

# --- django-allauth (social / Google OAuth) ---
# Token flow: the app obtains a Google id_token itself (web: OIDC implicit with
# the Web client id; Android/iOS: code+PKCE with the platform's installed-app
# client id) and POSTs it to /_allauth/app/v1/auth/provider/token. allauth
# selects the app whose client_id matches the posted token.client_id, verifies
# the id_token (issuer, signature, audience == that client_id), and issues the
# same JWT as the email/password flow.
#
# The Web app (id + secret) is primary. Installed-app clients carry no secret
# and are marked "hidden" so lookups without an explicit client_id (e.g. the
# config endpoint) unambiguously resolve to the Web app.
_google_oauth_apps = [
    {
        "client_id": SETTINGS.google_oauth_client_id,
        "secret": SETTINGS.google_oauth_client_secret,
        "key": "",
    },
    *(
        {"client_id": _client_id, "secret": "", "key": "", "settings": {"hidden": True}}
        for _client_id in (SETTINGS.google_oauth_android_client_id, SETTINGS.google_oauth_ios_client_id)
        if _client_id
    ),
]
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": _google_oauth_apps,
        "SCOPE": ["profile", "email"],
        # Trust Google's verified email so social sign-in skips the email-code stage.
        "EMAIL_AUTHENTICATION": True,
        "VERIFIED_EMAIL": True,
    }
}
# Promote the provider's full display name onto User.first_name (see adapter).
SOCIALACCOUNT_ADAPTER = "scraping.adapters.SocialAccountAdapter"
# Log the user into the existing account (and persist the link) when the verified
# provider email matches an existing verified account, instead of erroring on a
# duplicate address. Safe here: allauth email verification is mandatory and Google
# emails carry email_verified.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# --- CORS (django-cors-headers) ---
# Browser clients on a different origin (the web build, local dev) need CORS
# headers; native mobile builds don't enforce CORS. allauth headless carries
# JWTs in the Authorization header (not cookies), so credentials stay OFF.
# Real deployed web origins come from the env (comma-separated, scheme included);
# any localhost/127.0.0.1 port is allowed so local web dev "just works".
CORS_ALLOWED_ORIGINS = [o.strip() for o in SETTINGS.cors_allowed_origins.split(",") if o.strip()]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost(:\d+)?$",
    r"^http://127\.0\.0\.1(:\d+)?$",
]
CORS_ALLOW_HEADERS = (*default_headers, "x-session-token")

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
# Reply-To for transactional auth mail, injected by scraping.adapters.AccountAdapter.
EMAIL_REPLY_TO = SETTINGS.email_reply_to
# Base URL email templates prefix onto static asset paths (see
# scraping.context_processors.email_branding) so images resolve in mail clients.
EMAIL_ASSET_BASE_URL = SETTINGS.email_asset_base_url.rstrip("/")
