import os

import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for var in ["CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"]:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_celery_defaults_to_localhost_redis(clean_env):
    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://localhost:6379/0"
    assert s.celery_result_backend == "redis://localhost:6379/1"


def test_celery_urls_picked_up_from_env(clean_env):
    clean_env.setenv("CELERY_BROKER_URL", "redis://broker.example:6379/5")
    clean_env.setenv("CELERY_RESULT_BACKEND", "redis://broker.example:6379/6")

    from realty_api.env import Settings

    s = Settings()
    assert s.celery_broker_url == "redis://broker.example:6379/5"
    assert s.celery_result_backend == "redis://broker.example:6379/6"
