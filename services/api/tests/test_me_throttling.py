import pytest

from scraping.api import api
from scraping.throttling import UserMergeThrottle, UserWriteThrottle


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def _throttle_objects(throttle_cls):
    """Yield every throttle instance of `throttle_cls` bound to an operation.

    Ninja binds each throttle's rate at class-definition/instantiation time from
    settings, so overriding NINJA_DEFAULT_THROTTLE_RATES in a test would not
    reach the already-instantiated objects. Instead we reach the live instances
    and shrink `num_requests` directly, which is what the request path reads.
    """
    for _prefix, router in api._routers:
        for view in router.path_operations.values():
            for operation in view.operations:
                for throttle in operation.throttle_objects:
                    if isinstance(throttle, throttle_cls):
                        yield throttle


@pytest.fixture
def low_write_limit(monkeypatch):
    for throttle in _throttle_objects(UserWriteThrottle):
        monkeypatch.setattr(throttle, "num_requests", 2)
    return 2


@pytest.fixture
def low_merge_limit(monkeypatch):
    for throttle in _throttle_objects(UserMergeThrottle):
        monkeypatch.setattr(throttle, "num_requests", 2)
    return 2


@pytest.mark.django_db
class TestWriteThrottle:
    def _delete_favorite(self, client, headers):
        # DELETE on an unknown id still returns 204 and counts against the
        # shared user_write bucket, so no residence row is needed.
        return client.delete("/v1/me/favorites/1", headers=headers)

    def test_write_bucket_returns_429_when_exceeded(self, client, user_headers, low_write_limit):
        for _ in range(low_write_limit):
            assert self._delete_favorite(client, user_headers).status_code == 204
        assert self._delete_favorite(client, user_headers).status_code == 429

    def test_write_bucket_is_shared_across_write_endpoints(self, client, user_headers, low_write_limit):
        # First request lands on the notifications PUT, the rest on favorites
        # DELETE; the shared user_write bucket still trips after `num_requests`.
        payload = {"notifications": {"push": True}, "updated_at": "2026-07-13T00:00:00Z"}
        assert client.put("/v1/me/preferences/notifications", json=payload, headers=user_headers).status_code == 200
        assert self._delete_favorite(client, user_headers).status_code == 204
        assert self._delete_favorite(client, user_headers).status_code == 429

    def test_429_carries_retry_after_header(self, client, user_headers, low_write_limit):
        for _ in range(low_write_limit):
            self._delete_favorite(client, user_headers)
        response = self._delete_favorite(client, user_headers)
        assert response.status_code == 429
        assert int(response["Retry-After"]) >= 0


@pytest.mark.django_db
class TestMergeThrottle:
    def _merge(self, client, headers):
        return client.post("/v1/me/favorites/merge", json={"items": []}, headers=headers)

    def test_merge_bucket_returns_429_when_exceeded(self, client, user_headers, low_merge_limit):
        for _ in range(low_merge_limit):
            assert self._merge(client, user_headers).status_code == 200
        assert self._merge(client, user_headers).status_code == 429

    def test_merge_bucket_is_independent_from_write_bucket(
        self, client, user_headers, low_write_limit, low_merge_limit
    ):
        # Exhaust the write bucket; the merge bucket is a separate scope and
        # must still admit requests.
        for _ in range(low_write_limit):
            client.delete("/v1/me/favorites/1", headers=user_headers)
        assert client.delete("/v1/me/favorites/1", headers=user_headers).status_code == 429
        assert self._merge(client, user_headers).status_code == 200
