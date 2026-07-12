from allauth.headless.contrib.ninja.security import jwt_token_auth
from django.http import HttpRequest
from ninja.errors import HttpError


def resolve_jwt_user(request: HttpRequest, *, strict: bool):
    """Resolve the caller from a JWT bearer token. No token → anonymous (None).
    Valid token → the User (and request.user is set). Invalid/expired token →
    raises 401 when strict, else returns None (treated as anonymous).

    allauth's public jwt_token_auth returns None for BOTH a missing and an
    invalid token, so we split them by inspecting the Authorization header.
    """
    if not request.headers.get("Authorization", "").lower().startswith("bearer "):
        return None
    if jwt_token_auth(request) is None:
        if strict:
            raise HttpError(401, "invalid or expired token")
        return None
    return request.user
