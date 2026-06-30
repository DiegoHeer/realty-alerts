"""CACHES wiring for allauth rate limiting.

allauth's rate limiter uses ``CACHES["default"]``; under multiple workers it must
be a shared backend (Redis) or the per-process LocMemCache lets limits multiply.
The backend is derived from the Celery broker (see ``Settings.cache_url``).
"""

from realty_api.settings.base import _cache_config


def test_cache_config_uses_redis_when_url_present():
    cfg = _cache_config("redis://redis:6379/1")

    assert cfg["default"]["BACKEND"] == "django.core.cache.backends.redis.RedisCache"
    assert cfg["default"]["LOCATION"] == "redis://redis:6379/1"


def test_cache_config_falls_back_to_locmem_when_url_none():
    cfg = _cache_config(None)

    assert cfg["default"]["BACKEND"] == "django.core.cache.backends.locmem.LocMemCache"
