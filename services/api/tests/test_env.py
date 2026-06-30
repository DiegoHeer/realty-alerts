import pytest


@pytest.fixture
def clean_env(monkeypatch):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    return monkeypatch


def test_celery_broker_defaults_to_localhost_redis(clean_env):
    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://localhost:6379/0"


def test_celery_broker_picked_up_from_env(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "redis://broker.example:6379/5")

    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://broker.example:6379/5"


def test_cache_url_derives_db_one_from_broker(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

    from realty_api.env import Settings

    s = Settings()
    assert s.cache_url == "redis://localhost:6379/1"


def test_cache_url_preserves_credentials_host_and_port(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "redis://:secret@redis:6380/0")

    from realty_api.env import Settings

    s = Settings()
    assert s.cache_url == "redis://:secret@redis:6380/1"


def test_cache_url_preserves_rediss_scheme(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "rediss://redis:6379/3")

    from realty_api.env import Settings

    s = Settings()
    assert s.cache_url == "rediss://redis:6379/1"


def test_cache_url_is_none_for_non_redis_broker(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "memory://")

    from realty_api.env import Settings

    s = Settings()
    assert s.cache_url is None
