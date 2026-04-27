def test_celery_app_is_named_realty_api():
    from realty_api import celery_app

    assert celery_app.main == "realty_api"


def test_celery_app_uses_django_settings_broker():
    from django.conf import settings

    from realty_api import celery_app

    assert celery_app.conf.broker_url == settings.CELERY_BROKER_URL


def test_celery_app_uses_django_db_result_backend():
    from realty_api import celery_app

    assert celery_app.conf.result_backend == "django-db"
