"""Tests for DELETE /v1/me/account (self-service account deletion).

Covers the security contract (own-account-only, fresh re-auth required) and the
hard-delete cascade. The recent-reauthentication path exercises the allauth
JWT-session internals that `_recently_reauthenticated` relies on, so these tests
double as the canary for an allauth upgrade changing those internals.
"""

import time
from typing import cast

import pytest
from allauth.account.models import EmailAddress
from allauth.headless.tokens.strategies.jwt.internal import create_access_token
from django.contrib.auth.models import User
from django.contrib.sessions.backends.db import SessionStore
from django.utils import timezone

from accounts.models import Favorite, ResidenceView, UserPreferences
from scraping.models import Feedback, Residence
from tests.factories import ResidenceFactory

ACCOUNT_URL = "/v1/me/account"
TEST_PASSWORD = "testpass123!"  # matches the `test_user` fixture in conftest


def _headers_for(user: User, *, method: str = "socialaccount", age_seconds: float | None = None) -> dict[str, str]:
    """Bearer headers for `user`. When `age_seconds` is given, the token's session
    carries an authentication-method record that old (so the handler sees a recent
    — or stale — re-authentication); when None, the session is empty (no re-auth).
    """
    session = SessionStore()
    session.create()
    if age_seconds is not None:
        session["account_authentication_methods"] = [{"method": method, "at": time.time() - age_seconds}]
        session.save()
    return {"AUTHORIZATION": f"Bearer {create_access_token(user, session, {})}"}


def _social_user(email: str = "social@example.com") -> User:
    """A user who signed in via a social provider: no usable password."""
    user = User.objects.create_user(email=email, username=email)
    user.set_unusable_password()
    user.save()
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    # The AccountDeleteThrottle bucket lives in the process cache and is keyed by
    # user pk; pks repeat across transaction-rolled-back tests, so clear it between
    # tests to keep the tight 5/min limit from leaking. Mirrors test_me_throttling.
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_requires_auth(client):
    assert client.delete(ACCOUNT_URL).status_code == 401


@pytest.mark.django_db
def test_correct_password_deletes_account(client, test_user, user_headers):
    r = client.delete(ACCOUNT_URL, json={"password": TEST_PASSWORD}, headers=user_headers)
    assert r.status_code == 204
    assert not User.objects.filter(pk=test_user.pk).exists()


@pytest.mark.django_db
def test_wrong_password_is_rejected(client, test_user, user_headers):
    r = client.delete(ACCOUNT_URL, json={"password": "not-my-password"}, headers=user_headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "password_incorrect"
    assert User.objects.filter(pk=test_user.pk).exists()  # untouched


@pytest.mark.django_db
def test_password_is_compared_verbatim_not_stripped(client):
    # Leading/trailing spaces are valid password characters; the correct password
    # (with its spaces) must authenticate — i.e. the handler must not strip it.
    spaced = "  spaced pw  "
    user = User.objects.create_user(email="spacey@example.com", username="spacey@example.com", password=spaced)
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    headers = _headers_for(user)  # no recent re-auth, so the password is the only proof
    r = client.delete(ACCOUNT_URL, json={"password": spaced}, headers=headers)
    assert r.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_social_user_supplying_a_password_is_told_to_reauthenticate(client):
    # A social account has no usable password, so any password is meaningless —
    # the error must be reauthentication_required, not the misleading password_incorrect.
    user = _social_user()
    headers = _headers_for(user)  # no recent re-auth
    r = client.delete(ACCOUNT_URL, json={"password": "anything"}, headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "reauthentication_required"
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_no_proof_is_rejected(client, test_user, user_headers):
    # Valid token but no password and no recent re-auth (fresh empty session).
    r = client.delete(ACCOUNT_URL, json={}, headers=user_headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "reauthentication_required"
    assert User.objects.filter(pk=test_user.pk).exists()


@pytest.mark.django_db
def test_social_user_with_recent_reauth_deletes(client):
    # No usable password, so the password branch can't help — a fresh re-auth
    # recorded on the token's session is what authorizes the delete.
    user = _social_user()
    headers = _headers_for(user, age_seconds=1)
    r = client.delete(ACCOUNT_URL, json={}, headers=headers)
    assert r.status_code == 204
    assert not User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_social_user_with_stale_reauth_is_rejected(client):
    # Authenticated long ago (well beyond ACCOUNT_REAUTHENTICATION_TIMEOUT, 300s).
    user = _social_user()
    headers = _headers_for(user, age_seconds=10_000)
    r = client.delete(ACCOUNT_URL, json={}, headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "reauthentication_required"
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_correct_password_wins_even_without_recent_session(client, test_user, user_headers):
    # Belt-and-braces: user_headers carries an empty session (no recent re-auth),
    # so this proves the password branch alone authorizes deletion.
    r = client.delete(ACCOUNT_URL, json={"password": TEST_PASSWORD}, headers=user_headers)
    assert r.status_code == 204


@pytest.mark.django_db
def test_staff_account_cannot_self_delete(client):
    staff = User.objects.create_user(email="ops@example.com", username="ops@example.com", password=TEST_PASSWORD)
    staff.is_staff = True
    staff.save()
    EmailAddress.objects.create(user=staff, email=staff.email, verified=True, primary=True)
    headers = _headers_for(staff, age_seconds=1)  # even freshly re-authed
    r = client.delete(ACCOUNT_URL, json={"password": TEST_PASSWORD}, headers=headers)
    assert r.status_code == 403
    assert r.json()["detail"] == "staff_account"
    assert User.objects.filter(pk=staff.pk).exists()


@pytest.mark.django_db
def test_deletion_cascades_user_data_and_nulls_feedback(client, test_user, user_headers):
    residence = cast(Residence, ResidenceFactory())
    Favorite.objects.create(user=test_user, residence=residence, liked_at=timezone.now())
    ResidenceView.objects.create(user=test_user, residence=residence, viewed_at=timezone.now())
    UserPreferences.objects.create(user=test_user, search={"deal_type": "buy"})
    feedback = Feedback.objects.create(user=test_user, message="great app")

    r = client.delete(ACCOUNT_URL, json={"password": TEST_PASSWORD}, headers=user_headers)
    assert r.status_code == 204

    # Owned rows cascade away…
    assert not Favorite.objects.filter(residence=residence).exists()
    assert not ResidenceView.objects.filter(residence=residence).exists()
    assert not UserPreferences.objects.filter(user_id=test_user.pk).exists()
    # …but the residence itself is untouched, and feedback is retained + anonymized.
    assert Residence.objects.filter(pk=residence.pk).exists()
    feedback.refresh_from_db()
    assert feedback.user_id is None


@pytest.mark.django_db
def test_only_deletes_the_caller(client, test_user, user_headers):
    other = User.objects.create_user(email="other@example.com", username="other@example.com", password="pass12345!")
    EmailAddress.objects.create(user=other, email=other.email, verified=True, primary=True)
    residence = cast(Residence, ResidenceFactory())
    Favorite.objects.create(user=other, residence=residence, liked_at=timezone.now())

    r = client.delete(ACCOUNT_URL, json={"password": TEST_PASSWORD}, headers=user_headers)
    assert r.status_code == 204

    # The other account and its data survive — deletion is scoped to the JWT's user.
    assert User.objects.filter(pk=other.pk).exists()
    assert Favorite.objects.filter(user=other).exists()


@pytest.mark.django_db
def test_repeated_attempts_are_tightly_throttled(client, test_user, user_headers):
    # Wrong-password attempts don't delete, so they'd otherwise let the endpoint be
    # used as a password-guessing oracle; the dedicated bucket (5/min) cuts it off.
    for _ in range(5):
        assert client.delete(ACCOUNT_URL, json={"password": "nope"}, headers=user_headers).status_code == 403
    assert client.delete(ACCOUNT_URL, json={"password": "nope"}, headers=user_headers).status_code == 429
