import pytest


@pytest.mark.django_db
class TestV1AuthRequired:
    """All v1 endpoints must return 401 without a valid JWT."""

    @pytest.mark.parametrize(
        "path",
        [
            "/v1/residences",
            "/v1/cities",
            "/v1/stats/cities/0518",
            "/v1/stats/districts?city=0518",
            "/v1/stats/neighborhoods?city=0518",
            "/v1/shapes/cities",
            "/v1/shapes/districts",
            "/v1/shapes/neighborhoods",
        ],
    )
    def test_returns_401_without_token(self, client, path):
        response = client.get(path)
        assert response.status_code == 401
