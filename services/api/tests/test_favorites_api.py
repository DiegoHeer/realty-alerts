from datetime import UTC, datetime
from typing import cast

import pytest

from accounts.models import Favorite
from scraping.models import Residence
from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
def test_favorites_requires_auth(client):
    assert client.get("/v1/me/favorites").status_code == 401


@pytest.mark.django_db
def test_put_then_get_hydrates_summary(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    ListingFactory(residence=residence, image_url="https://example.com/c.jpg")
    ts = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
    r = client.put(f"/v1/me/favorites/{residence.pk}", json={"liked_at": ts}, headers=user_headers)
    assert r.status_code == 204
    body = client.get("/v1/me/favorites", headers=user_headers).json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["residence"]["id"] == residence.pk
    assert item["residence"]["image_url"] == "https://example.com/c.jpg"  # annotation hydrated
    assert item["liked_at"] is not None


@pytest.mark.django_db
def test_get_orders_newest_liked_first(client, user_headers):
    older = cast(Residence, ResidenceFactory())
    newer = cast(Residence, ResidenceFactory())
    client.put(
        f"/v1/me/favorites/{older.pk}",
        json={"liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
        headers=user_headers,
    )
    client.put(
        f"/v1/me/favorites/{newer.pk}",
        json={"liked_at": datetime(2026, 2, 1, tzinfo=UTC).isoformat()},
        headers=user_headers,
    )
    items = client.get("/v1/me/favorites", headers=user_headers).json()["items"]
    assert [i["residence"]["id"] for i in items] == [newer.pk, older.pk]


@pytest.mark.django_db
def test_put_unknown_residence_404(client, user_headers):
    r = client.put("/v1/me/favorites/999999", json={}, headers=user_headers)
    assert r.status_code == 404


@pytest.mark.django_db
def test_put_rejects_naive_liked_at(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    r = client.put(f"/v1/me/favorites/{residence.pk}", json={"liked_at": "2026-01-01T00:00:00"}, headers=user_headers)
    assert r.status_code == 422


@pytest.mark.django_db
def test_put_without_liked_at_defaults_now(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    r = client.put(f"/v1/me/favorites/{residence.pk}", json={}, headers=user_headers)
    assert r.status_code == 204
    assert Favorite.objects.filter(user__isnull=False, residence=residence).exists()


@pytest.mark.django_db
def test_delete_is_idempotent(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    client.put(f"/v1/me/favorites/{residence.pk}", json={}, headers=user_headers)
    assert client.delete(f"/v1/me/favorites/{residence.pk}", headers=user_headers).status_code == 204
    assert (
        client.delete(f"/v1/me/favorites/{residence.pk}", headers=user_headers).status_code == 204
    )  # again → still 204
    assert not Favorite.objects.filter(residence=residence).exists()


@pytest.mark.django_db
def test_favorites_isolated_between_users(client, test_user, user_headers):
    from allauth.account.models import EmailAddress
    from allauth.headless.tokens.strategies.jwt.internal import create_access_token
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore

    residence = cast(Residence, ResidenceFactory())
    client.put(f"/v1/me/favorites/{residence.pk}", json={}, headers=user_headers)
    user_b = User.objects.create_user(email="b@example.com", username="b@example.com", password="pass12345!")
    EmailAddress.objects.create(user=user_b, email=user_b.email, verified=True, primary=True)
    session = SessionStore()
    session.create()
    headers_b = {"AUTHORIZATION": f"Bearer {create_access_token(user_b, session, {})}"}
    assert client.get("/v1/me/favorites", headers=headers_b).json() == {"items": [], "total": 0}


@pytest.mark.django_db
def test_merge_unions_and_keeps_newer(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    client.put(
        f"/v1/me/favorites/{residence.pk}",
        json={"liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
        headers=user_headers,
    )
    body = client.post(
        "/v1/me/favorites/merge",
        json={"items": [{"residence_id": residence.pk, "liked_at": datetime(2026, 3, 1, tzinfo=UTC).isoformat()}]},
        headers=user_headers,
    ).json()
    assert body["total"] == 1
    from accounts.models import Favorite

    favorite = Favorite.objects.get(residence=residence)
    assert favorite.liked_at.year == 2026 and favorite.liked_at.month == 3


@pytest.mark.django_db
def test_merge_skips_unknown_residence_ids(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    body = client.post(
        "/v1/me/favorites/merge",
        json={
            "items": [
                {"residence_id": residence.pk, "liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
                {"residence_id": 999999, "liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()},
            ]
        },
        headers=user_headers,
    ).json()
    assert body["total"] == 1  # unknown id skipped, not an error


@pytest.mark.django_db
def test_merge_rejects_over_cap(client, user_headers):
    items = [{"residence_id": n, "liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()} for n in range(201)]
    r = client.post("/v1/me/favorites/merge", json={"items": items}, headers=user_headers)
    assert r.status_code == 422


@pytest.mark.django_db
def test_merge_is_idempotent(client, user_headers):
    residence = cast(Residence, ResidenceFactory())
    payload = {"items": [{"residence_id": residence.pk, "liked_at": datetime(2026, 1, 1, tzinfo=UTC).isoformat()}]}
    first = client.post("/v1/me/favorites/merge", json=payload, headers=user_headers).json()
    second = client.post("/v1/me/favorites/merge", json=payload, headers=user_headers).json()
    assert first == second and second["total"] == 1


@pytest.mark.django_db
def test_get_favorites_skips_null_coordinate_residence(client, user_headers):
    residence = cast(Residence, ResidenceFactory(latitude=None, longitude=None))
    r = client.put(f"/v1/me/favorites/{residence.pk}", json={}, headers=user_headers)
    assert r.status_code == 204
    resp = client.get("/v1/me/favorites", headers=user_headers)
    assert resp.status_code == 200  # must not 500 on the null-coord favorite
    assert resp.json() == {"items": [], "total": 0}  # silently dropped, like a missing residence
