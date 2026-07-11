from allauth.headless.tokens.strategies.jwt.internal import validate_access_token
from ninja.security import HttpBearer


class JWTAuth(HttpBearer):
    def authenticate(self, request, token):
        result = validate_access_token(token)
        if result is None:
            return None
        request.user, _payload = result
        return request.user
