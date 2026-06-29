import json

import pytest
from django.http import HttpResponse
from django.test import Client as DjangoTestClient

SIGNUP_URL = "/_allauth/app/v1/auth/signup"


def _post(client: DjangoTestClient, url: str, payload: dict) -> HttpResponse:
    return client.post(url, data=json.dumps(payload), content_type="application/json")


@pytest.fixture
def headless_client() -> DjangoTestClient:
    return DjangoTestClient()


@pytest.mark.django_db
class TestSignupName:
    def test_signup_persists_name_as_first_name(self, headless_client):
        from django.contrib.auth.models import User

        _post(
            headless_client,
            SIGNUP_URL,
            {"email": "newuser@example.com", "name": "Ada Lovelace", "password": "sup3rs3cret!"},
        )

        user = User.objects.get(email="newuser@example.com")
        assert user.first_name == "Ada Lovelace"
        assert user.last_name == ""

    def test_signup_rejects_missing_name(self, headless_client):
        response = _post(
            headless_client,
            SIGNUP_URL,
            {"email": "noname@example.com", "password": "sup3rs3cret!"},
        )

        assert response.status_code == 400

    def test_signup_rejects_missing_email(self, headless_client):
        response = _post(
            headless_client,
            SIGNUP_URL,
            {"name": "No Email", "password": "sup3rs3cret!"},
        )

        assert response.status_code == 400

    def test_signup_rejects_missing_password(self, headless_client):
        response = _post(
            headless_client,
            SIGNUP_URL,
            {"email": "nopw@example.com", "name": "No Password"},
        )

        assert response.status_code == 400
