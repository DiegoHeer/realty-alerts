import json

import pytest
from django.core import mail
from django.http import HttpResponse
from django.test import Client as DjangoTestClient
from django.test import override_settings

SIGNUP_URL = "/_allauth/app/v1/auth/signup"
LOGIN_URL = "/_allauth/app/v1/auth/login"
SESSION_URL = "/_allauth/app/v1/auth/session"


def _post(client: DjangoTestClient, url: str, payload: dict) -> HttpResponse:
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _body(response: HttpResponse) -> dict:
    return json.loads(response.content)


@pytest.fixture
def headless_client() -> DjangoTestClient:
    return DjangoTestClient()


@pytest.fixture
def verified_user():
    from allauth.account.models import EmailAddress
    from django.contrib.auth.models import User

    user = User.objects.create_user(
        email="grace@example.com",
        username="grace@example.com",
        password="testpass123!",
        first_name="Grace Hopper",
    )
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


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


@pytest.mark.django_db
class TestVerificationEmail:
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_sends_verification_email(self, headless_client):
        _post(
            headless_client,
            SIGNUP_URL,
            {"email": "verify@example.com", "name": "Ada Lovelace", "password": "sup3rs3cret!"},
        )

        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["verify@example.com"]


@pytest.mark.django_db
class TestUserObjectName:
    def test_login_user_object_includes_name(self, headless_client, verified_user):
        response = _post(
            headless_client,
            LOGIN_URL,
            {"email": verified_user.email, "password": "testpass123!"},
        )

        assert response.status_code == 200
        assert _body(response)["data"]["user"]["name"] == "Grace Hopper"

    def test_session_user_object_includes_name(self, headless_client, verified_user):
        login = _post(
            headless_client,
            LOGIN_URL,
            {"email": verified_user.email, "password": "testpass123!"},
        )
        access_token = _body(login)["meta"]["access_token"]

        response = headless_client.get(SESSION_URL, headers={"Authorization": f"Bearer {access_token}"})

        assert response.status_code == 200
        assert _body(response)["data"]["user"]["name"] == "Grace Hopper"
