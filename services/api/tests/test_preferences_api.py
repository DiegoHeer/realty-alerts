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
