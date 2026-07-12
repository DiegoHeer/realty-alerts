from typing import cast

import pytest

from accounts.models import ResidenceView
from scraping.models import Residence
from tests.factories import ListingFactory, ResidenceFactory


@pytest.mark.django_db
def test_recent_views_requires_auth(client):
    assert client.get("/v1/me/recent-views").status_code == 401


@pytest.mark.django_db
def test_post_then_get_hydrates_and_orders(client, user_headers):
    first = cast(Residence, ResidenceFactory())
    second = cast(Residence, ResidenceFactory())
    ListingFactory(residence=second, image_url="https://example.com/c.jpg")
    assert client.post(f"/v1/me/recent-views/{first.pk}", headers=user_headers).status_code == 204
    assert client.post(f"/v1/me/recent-views/{second.pk}", headers=user_headers).status_code == 204
    body = client.get("/v1/me/recent-views", headers=user_headers).json()
    assert body["total"] == 2
    assert [i["residence"]["id"] for i in body["items"]] == [second.pk, first.pk]  # newest-viewed first
    assert body["items"][0]["residence"]["image_url"] == "https://example.com/c.jpg"
    assert body["items"][0]["viewed_at"] is not None


@pytest.mark.django_db
def test_reposting_moves_to_front(client, user_headers):
    a = cast(Residence, ResidenceFactory())
    b = cast(Residence, ResidenceFactory())
    client.post(f"/v1/me/recent-views/{a.pk}", headers=user_headers)
    client.post(f"/v1/me/recent-views/{b.pk}", headers=user_headers)
    client.post(f"/v1/me/recent-views/{a.pk}", headers=user_headers)  # re-view a
    ids = [i["residence"]["id"] for i in client.get("/v1/me/recent-views", headers=user_headers).json()["items"]]
    assert ids == [a.pk, b.pk]  # a moved to front, still only 2 rows
    assert ResidenceView.objects.count() == 2


@pytest.mark.django_db
def test_post_unknown_residence_404(client, user_headers):
    assert client.post("/v1/me/recent-views/999999", headers=user_headers).status_code == 404


@pytest.mark.django_db
def test_evicts_beyond_twelve(client, user_headers):
    ids = [cast(Residence, ResidenceFactory()).pk for _ in range(13)]
    for residence_id in ids:
        client.post(f"/v1/me/recent-views/{residence_id}", headers=user_headers)
    body = client.get("/v1/me/recent-views", headers=user_headers).json()
    assert body["total"] == 12
    assert ids[0] not in [i["residence"]["id"] for i in body["items"]]  # oldest evicted


@pytest.mark.django_db
def test_delete_clears_all(client, user_headers):
    for _ in range(3):
        client.post(f"/v1/me/recent-views/{cast(Residence, ResidenceFactory()).pk}", headers=user_headers)
    assert client.delete("/v1/me/recent-views", headers=user_headers).status_code == 204
    assert client.get("/v1/me/recent-views", headers=user_headers).json() == {"items": [], "total": 0}


@pytest.mark.django_db
def test_get_skips_null_coordinate_residence(client, user_headers):
    residence = cast(Residence, ResidenceFactory(latitude=None, longitude=None))
    assert client.post(f"/v1/me/recent-views/{residence.pk}", headers=user_headers).status_code == 204
    resp = client.get("/v1/me/recent-views", headers=user_headers)
    assert resp.status_code == 200
    assert resp.json() == {"items": [], "total": 0}


@pytest.mark.django_db
def test_recent_views_isolated_between_users(client, test_user, user_headers):
    from allauth.account.models import EmailAddress
    from allauth.headless.tokens.strategies.jwt.internal import create_access_token
    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.db import SessionStore

    client.post(f"/v1/me/recent-views/{cast(Residence, ResidenceFactory()).pk}", headers=user_headers)
    user_b = User.objects.create_user(email="b@example.com", username="b@example.com", password="pass12345!")
    EmailAddress.objects.create(user=user_b, email=user_b.email, verified=True, primary=True)
    session = SessionStore()
    session.create()
    headers_b = {"AUTHORIZATION": f"Bearer {create_access_token(user_b, session, {})}"}
    assert client.get("/v1/me/recent-views", headers=headers_b).json() == {"items": [], "total": 0}
