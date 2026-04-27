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
