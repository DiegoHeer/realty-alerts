import json
import re

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponse
from django.test import Client as DjangoTestClient
from django.test import override_settings

SIGNUP_URL = "/_allauth/app/v1/auth/signup"
LOGIN_URL = "/_allauth/app/v1/auth/login"
SESSION_URL = "/_allauth/app/v1/auth/session"
PASSWORD_REQUEST_URL = "/_allauth/app/v1/auth/password/request"
PASSWORD_RESET_URL = "/_allauth/app/v1/auth/password/reset"
PASSWORD_CHANGE_URL = "/_allauth/app/v1/account/password/change"


def _post(client: DjangoTestClient, url: str, payload: dict) -> HttpResponse:
    return client.post(url, data=json.dumps(payload), content_type="application/json")


def _body(response: HttpResponse) -> dict:
    return json.loads(response.content)


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


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

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_REPLY_TO="support@huismusapp.com",
    )
    def test_verification_email_sets_reply_to_when_configured(self, headless_client):
        _post(
            headless_client,
            SIGNUP_URL,
            {"email": "verify@example.com", "name": "Ada Lovelace", "password": "sup3rs3cret!"},
        )

        assert mail.outbox[0].reply_to == ["support@huismusapp.com"]

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        EMAIL_REPLY_TO="",
    )
    def test_verification_email_omits_reply_to_when_unset(self, headless_client):
        _post(
            headless_client,
            SIGNUP_URL,
            {"email": "verify@example.com", "name": "Ada Lovelace", "password": "sup3rs3cret!"},
        )

        assert mail.outbox[0].reply_to == []


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


@pytest.mark.django_db
class TestPasswordResetByCode:
    """Reset must work by code; the link flow 500s without HEADLESS_FRONTEND_URLS."""

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_request_sends_email_not_500(self, headless_client, verified_user):
        response = _post(headless_client, PASSWORD_REQUEST_URL, {"email": verified_user.email})

        # By-code request returns an unauthenticated AuthenticationResponse (401) with a
        # pending flow + session token — the regression was a 500 here. Email must be sent.
        assert response.status_code == 401
        assert _body(response)["meta"]["session_token"]
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [verified_user.email]

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_full_reset_by_code_flow(self, headless_client, verified_user):
        request = _post(headless_client, PASSWORD_REQUEST_URL, {"email": verified_user.email})
        session_token = _body(request)["meta"]["session_token"]

        match = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}", mail.outbox[0].body)
        assert match, f"no reset code found in email body:\n{mail.outbox[0].body}"
        code = match.group(0)

        reset = headless_client.post(
            PASSWORD_RESET_URL,
            data=json.dumps({"key": code, "password": "Rel0cated!pw"}),
            content_type="application/json",
            headers={"X-Session-Token": session_token},
        )
        assert reset.status_code != 400  # code accepted (not an invalid-key error)

        # The real proof the reset took effect: old password rejected, new password accepted.
        old = _post(headless_client, LOGIN_URL, {"email": verified_user.email, "password": "testpass123!"})
        new = _post(headless_client, LOGIN_URL, {"email": verified_user.email, "password": "Rel0cated!pw"})
        assert old.status_code != 200
        assert new.status_code == 200

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_code_survives_realistic_email_delay(self, headless_client, verified_user, monkeypatch):
        """A code entered minutes after the email arrives must still be accepted.

        allauth's default PASSWORD_RESET_BY_CODE_TIMEOUT is 3 minutes — shorter than a
        real SMTP round-trip plus the user switching apps to read the code, so every
        reset failed with "invalid or expired". This guards the configured window by
        advancing allauth's clock 5 minutes between request and submit (past the old
        3-minute default, within the configured one).
        """
        from allauth.account.internal.flows import code_verification

        clock = {"now": 1_000_000.0}

        class _FakeClock:
            def time(self) -> float:
                return clock["now"]

        # code_verification stamps the code's "at" and checks its age via this module's
        # `time`; swapping it lets us control the elapsed time deterministically.
        monkeypatch.setattr(code_verification, "time", _FakeClock())

        request = _post(headless_client, PASSWORD_REQUEST_URL, {"email": verified_user.email})
        session_token = _body(request)["meta"]["session_token"]

        match = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}", mail.outbox[0].body)
        assert match, f"no reset code found in email body:\n{mail.outbox[0].body}"
        code = match.group(0)

        clock["now"] += 5 * 60  # 5 minutes pass before the user submits the code

        reset = headless_client.post(
            PASSWORD_RESET_URL,
            data=json.dumps({"key": code, "password": "Rel0cated!pw"}),
            content_type="application/json",
            headers={"X-Session-Token": session_token},
        )

        new = _post(headless_client, LOGIN_URL, {"email": verified_user.email, "password": "Rel0cated!pw"})
        assert new.status_code == 200, f"reset rejected after 5 min: {reset.status_code} {reset.content!r}"


@pytest.mark.django_db
class TestPasswordResetEmailHtml:
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_reset_request_sends_multipart_branded_email(self, headless_client, verified_user):
        _post(headless_client, PASSWORD_REQUEST_URL, {"email": verified_user.email})

        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert isinstance(msg, EmailMultiAlternatives)
        # HTML alternative present and MJML-compiled:
        assert msg.alternatives, "expected an HTML alternative"
        html, mime = msg.alternatives[0]
        assert isinstance(html, str)
        assert mime == "text/html"
        assert "<html" in html.lower()
        assert "Huismus" in html
        # code appears in both parts:
        match = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}", msg.body)
        assert match is not None
        code = match.group()
        assert code in html


@pytest.mark.django_db
class TestPasswordChangedNotification:
    """ACCOUNT_EMAIL_NOTIFICATIONS must be True or allauth silently drops this mail.

    Regression coverage for the bug where the security-notice emails
    (password/email changed, email deleted) were rendered and tested but never
    actually sent because ACCOUNT_EMAIL_NOTIFICATIONS was left at its default (False).
    """

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_change_sends_branded_security_notice(self, headless_client, verified_user):
        login = _post(headless_client, LOGIN_URL, {"email": verified_user.email, "password": "testpass123!"})
        access_token = _body(login)["meta"]["access_token"]

        response = headless_client.post(
            PASSWORD_CHANGE_URL,
            data=json.dumps({"current_password": "testpass123!", "new_password": "Rel0cated!pw"}),
            content_type="application/json",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        assert response.status_code == 200
        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert isinstance(msg, EmailMultiAlternatives)
        assert msg.to == [verified_user.email]
        assert msg.alternatives, "expected an HTML alternative"
        html, mime = msg.alternatives[0]
        assert isinstance(html, str)
        assert mime == "text/html"
        assert "Huismus" in html
        assert "Your password was changed" in html


@pytest.mark.django_db
class TestVerificationEmailHtml:
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_signup_sends_multipart_branded_email(self, headless_client):
        _post(
            headless_client,
            SIGNUP_URL,
            {"email": "html@example.com", "name": "Ada", "password": "sup3rs3cret!"},
        )
        assert len(mail.outbox) == 1
        msg = mail.outbox[0]
        assert isinstance(msg, EmailMultiAlternatives)
        assert msg.from_email == "Huismus <noreply@huismusapp.com>"
        # HTML alternative present and MJML-compiled:
        assert msg.alternatives, "expected an HTML alternative"
        html, mime = msg.alternatives[0]
        assert isinstance(html, str)
        assert mime == "text/html"
        assert "<html" in html.lower()
        assert "Huismus" in html
        # code appears in both parts:
        match = re.search(r"[A-Z0-9]{4}-[A-Z0-9]{4}", msg.body)
        assert match is not None
        code = match.group()
        assert code in html
