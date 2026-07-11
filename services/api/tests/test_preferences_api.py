from datetime import UTC, datetime, timedelta

import pytest


@pytest.mark.django_db
def test_get_search_requires_auth(client):
    resp = client.get("/v1/me/preferences/search")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_get_search_empty_when_unset(client, user_headers):
    resp = client.get("/v1/me/preferences/search", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == {"search": None, "updated_at": None}


@pytest.mark.django_db
def test_put_search_stores_and_returns(client, user_headers):
    ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    body = {"search": {"price_max": 500000, "city": "Amsterdam"}, "updated_at": ts}
    resp = client.put("/v1/me/preferences/search", json=body, headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["search"] == {"price_max": 500000, "city": "Amsterdam"}


@pytest.mark.django_db
def test_put_search_lww_rejects_stale(client, user_headers):
    newer = datetime(2026, 2, 1, tzinfo=UTC)
    older = newer - timedelta(days=10)
    client.put(
        "/v1/me/preferences/search",
        json={"search": {"v": "new"}, "updated_at": newer.isoformat()},
        headers=user_headers,
    )
    resp = client.put(
        "/v1/me/preferences/search",
        json={"search": {"v": "stale"}, "updated_at": older.isoformat()},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["search"] == {"v": "new"}  # winning (newer) doc returned unchanged


@pytest.mark.django_db
def test_put_search_rejects_oversized(client, user_headers):
    big = {"k": "x" * 5000}
    resp = client.put(
        "/v1/me/preferences/search",
        json={"search": big, "updated_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
        headers=user_headers,
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_put_search_empty_dict_roundtrips(client, user_headers):
    ts = datetime(2026, 4, 1, tzinfo=UTC).isoformat()
    client.put("/v1/me/preferences/search", json={"search": {}, "updated_at": ts}, headers=user_headers)
    resp = client.get("/v1/me/preferences/search", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json()["search"] == {}  # explicitly-set empty filter, not null
    assert resp.json()["updated_at"] is not None


@pytest.mark.django_db
def test_get_notifications_empty_when_unset(client, user_headers):
    resp = client.get("/v1/me/preferences/notifications", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == {"notifications": None, "updated_at": None}


@pytest.mark.django_db
def test_put_notifications_lww(client, user_headers):
    newer = datetime(2026, 3, 1, tzinfo=UTC)
    older = newer - timedelta(days=5)
    client.put(
        "/v1/me/preferences/notifications",
        json={"notifications": {"email": True}, "updated_at": newer.isoformat()},
        headers=user_headers,
    )
    resp = client.put(
        "/v1/me/preferences/notifications",
        json={"notifications": {"email": False}, "updated_at": older.isoformat()},
        headers=user_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["notifications"] == {"email": True}


@pytest.mark.django_db
def test_notifications_requires_auth(client):
    assert client.get("/v1/me/preferences/notifications").status_code == 401


@pytest.mark.django_db
def test_search_preferences_isolated_between_users(client, test_user, user_headers):
    from allauth.account.models import EmailAddress
    from allauth.headless.tokens.strategies.jwt.internal import create_access_token
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore

    ts = datetime(2026, 5, 1, tzinfo=UTC).isoformat()
    client.put(
        "/v1/me/preferences/search",
        json={"search": {"owner": "A"}, "updated_at": ts},
        headers=user_headers,
    )

    user_b = User.objects.create_user(email="b@example.com", username="b@example.com", password="pass12345!")
    EmailAddress.objects.create(user=user_b, email=user_b.email, verified=True, primary=True)
    session = SessionStore()
    session.create()
    token_b = create_access_token(user_b, session, {})
    headers_b = {"AUTHORIZATION": f"Bearer {token_b}"}

    resp_b = client.get("/v1/me/preferences/search", headers=headers_b)
    assert resp_b.json() == {"search": None, "updated_at": None}

    resp_a = client.get("/v1/me/preferences/search", headers=user_headers)
    assert resp_a.json()["search"] == {"owner": "A"}
