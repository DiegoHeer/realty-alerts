import json
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.test import Client as DjangoTestClient

PROVIDER_TOKEN_URL = "/_allauth/app/v1/auth/provider/token"
LOGIN_URL = "/_allauth/app/v1/auth/login"

# Must match GOOGLE_SETTINGS["google"]["APPS"][0]["client_id"]: the ProviderToken
# validator rejects a token whose client_id != the configured app client_id, and
# _verify_and_decode checks the id_token audience against it.
TEST_CLIENT_ID = "test-web-client-id.apps.googleusercontent.com"

GOOGLE_SETTINGS = {
    "google": {
        "APPS": [{"client_id": TEST_CLIENT_ID, "secret": "test-secret", "key": ""}],
        "SCOPE": ["profile", "email"],
        "EMAIL_AUTHENTICATION": True,
        "VERIFIED_EMAIL": True,
    }
}


def _google_identity(
    email="ada@gmail.com",
    sub="google-sub-123",
    name="Ada Lovelace",
    given="Ada",
    family="Lovelace",
    verified=True,
):
    """The decoded id_token payload _verify_and_decode returns for Google."""
    return {
        "iss": "https://accounts.google.com",
        "aud": TEST_CLIENT_ID,
        "sub": sub,
        "email": email,
        "email_verified": verified,
        "name": name,
        "given_name": given,
        "family_name": family,
    }


@pytest.fixture
def headless_client() -> DjangoTestClient:
    return DjangoTestClient()


def _post_google_token(client: DjangoTestClient, identity: dict) -> HttpResponse:
    payload = {
        "provider": "google",
        "process": "login",
        "token": {"client_id": TEST_CLIENT_ID, "id_token": "fake-id-token"},
    }
    with patch(
        "allauth.socialaccount.providers.google.views._verify_and_decode",
        return_value=identity,
    ):
        return client.post(PROVIDER_TOKEN_URL, data=json.dumps(payload), content_type="application/json")


def _body(response: HttpResponse) -> dict:
    return json.loads(response.content)


@pytest.mark.django_db
class TestProviderTokenLogin:
    @pytest.fixture(autouse=True)
    def _google_settings(self, settings):
        settings.SOCIALACCOUNT_PROVIDERS = GOOGLE_SETTINGS

    def test_new_user_login_returns_jwt_and_creates_user(self, headless_client):
        from django.contrib.auth.models import User

        response = _post_google_token(headless_client, _google_identity())

        assert response.status_code == 200, response.content
        body = _body(response)
        assert body["meta"]["access_token"]
        assert body["meta"]["refresh_token"]
        assert body["data"]["user"]["email"] == "ada@gmail.com"
        assert User.objects.filter(email="ada@gmail.com").count() == 1

    def test_googles_verified_email_skips_verification_stage(self, headless_client):
        from allauth.account.models import EmailAddress

        response = _post_google_token(headless_client, _google_identity())

        assert response.status_code == 200, response.content
        assert EmailAddress.objects.filter(email="ada@gmail.com", verified=True).exists()

    def test_user_object_includes_full_display_name(self, headless_client):
        response = _post_google_token(
            headless_client, _google_identity(name="Ada Lovelace", given="Ada", family="Lovelace")
        )

        assert response.status_code == 200, response.content
        # Google's extract_common_fields sets first_name=given_name ("Ada") only;
        # the adapter must promote the full display name so `name` matches the
        # email/password path (which stores the full name in first_name).
        assert _body(response)["data"]["user"]["name"] == "Ada Lovelace"

    def test_links_existing_verified_email_user_without_duplicate(self, headless_client):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount
        from django.contrib.auth.models import User

        existing = User.objects.create_user(
            email="ada@gmail.com",
            username="ada@gmail.com",
            password="testpass123!",
            first_name="Ada Lovelace",
        )
        EmailAddress.objects.create(user=existing, email=existing.email, verified=True, primary=True)

        response = _post_google_token(headless_client, _google_identity(email="ada@gmail.com"))

        assert response.status_code == 200, response.content
        assert User.objects.filter(email="ada@gmail.com").count() == 1
        assert SocialAccount.objects.filter(user=existing, provider="google").exists()

    def test_invalid_token_is_rejected(self, headless_client):
        from allauth.socialaccount.providers.oauth2.client import OAuth2Error

        payload = {
            "provider": "google",
            "process": "login",
            "token": {"client_id": TEST_CLIENT_ID, "id_token": "bad"},
        }

        # The Google provider catches OAuth2Error/RequestException from token
        # verification and re-raises it as an allauth "invalid_token" validation error.
        with patch(
            "allauth.socialaccount.providers.google.views._verify_and_decode",
            side_effect=OAuth2Error("bad token"),
        ):
            response = headless_client.post(
                PROVIDER_TOKEN_URL, data=json.dumps(payload), content_type="application/json"
            )

        assert response.status_code in (400, 401)
