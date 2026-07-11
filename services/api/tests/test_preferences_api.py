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
