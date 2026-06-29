import pytest
from allauth.headless.contrib.ninja.security import jwt_token_auth
from ninja import NinjaAPI
from ninja.testing import TestClient


@pytest.fixture
def protected_client() -> TestClient:
    """A throwaway API with a single jwt_token_auth-protected route.

    V1 endpoints are intentionally public, so this stand-in route is what
    exercises the JWT infrastructure (token issuance + jwt_token_auth) that
    future gated endpoints will rely on.
    """
    api = NinjaAPI(urls_namespace="test_jwt_auth")

    @api.get("/protected", auth=jwt_token_auth)
    def _protected(request):
        return {"user_id": request.user.pk}

    return TestClient(api)


@pytest.mark.django_db
class TestJWTTokenAuth:
    def test_rejects_request_without_token(self, protected_client):
        response = protected_client.get("/protected")

        assert response.status_code == 401

    def test_rejects_invalid_token(self, protected_client):
        response = protected_client.get("/protected", headers={"AUTHORIZATION": "Bearer not-a-jwt"})

        assert response.status_code == 401

    def test_accepts_valid_token(self, protected_client, user_headers, test_user):
        response = protected_client.get("/protected", headers=user_headers)

        assert response.status_code == 200
        assert response.json()["user_id"] == test_user.pk


@pytest.mark.django_db
class TestAdminLogin:
    """ModelBackend must stay registered so the Django admin keeps accepting
    username/password — allauth's email-only backend cannot serve admin login.
    """

    def test_superuser_can_log_into_admin(self):
        from django.contrib.auth.models import User
        from django.test import Client as DjangoTestClient

        User.objects.create_superuser("admin", "admin@example.com", "testpass123!")
        tc = DjangoTestClient()

        logged_in = tc.login(username="admin", password="testpass123!")

        assert logged_in
        response = tc.get("/admin/")
        assert response.status_code == 200
