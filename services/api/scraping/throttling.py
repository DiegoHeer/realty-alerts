from allauth.account.adapter import get_adapter
from allauth.headless.contrib.ninja.security import jwt_token_auth
from django.http import HttpRequest
from loguru import logger
from ninja.errors import HttpError
from ninja.throttling import SimpleRateThrottle, UserRateThrottle


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


class FeedbackThrottle(SimpleRateThrottle):
    """Rate-limit feedback per user (valid JWT) else per client IP.

    Resolves identity itself because the endpoint is auth=None (JWT is handled
    in the handler), and keys IPs off CF-Connecting-IP via the allauth adapter
    rather than Ninja's REMOTE_ADDR/X-Forwarded-For. Fails open if the cache is
    unavailable so an outage never blocks legitimate submissions.

    Only cache errors fail open. An anonymous request whose client IP can't be
    resolved is rejected (the adapter raises): in prod that means a missing
    CF-Connecting-IP, i.e. traffic that bypassed the Cloudflare edge. Dev/CI
    don't set the trusted header, so they fall back to REMOTE_ADDR.

    Stashes per-request state on the shared instance; safe only under sync
    workers (one request per process).
    """

    ANON_RATE = "3/h"
    USER_RATE = "10/h"

    def __init__(self):
        # Rate is chosen per-request in allow_request(); skip the base __init__
        # which would require a fixed rate/scope up front.
        pass

    def allow_request(self, request):
        user = resolve_jwt_user(request, strict=False)
        if user is not None:
            self.num_requests, self.duration = self.parse_rate(self.USER_RATE)
            self._ident = f"user:{user.pk}"
        else:
            self.num_requests, self.duration = self.parse_rate(self.ANON_RATE)
            self._ident = f"ip:{get_adapter().get_client_ip(request)}"
        try:
            return super().allow_request(request)
        except Exception:  # cache down/hiccup → don't block legitimate users
            logger.warning("feedback throttle failing open (cache error)")
            return True

    def get_cache_key(self, request):
        return f"throttle_feedback_{self._ident}"


class UserWriteThrottle(UserRateThrottle):
    """Rate-limit authenticated write requests per user.

    Shared bucket across favorites/preferences/recent-views writes. Keys off
    request.user.pk (me_router sets it before throttle checks); the rate comes
    from settings.NINJA_DEFAULT_THROTTLE_RATES["user_write"].
    """

    scope = "user_write"


class UserMergeThrottle(UserRateThrottle):
    """Rate-limit the favorites bulk-merge per user.

    Separate, tighter bucket than UserWriteThrottle because a merge writes many
    rows at once. Rate comes from settings.NINJA_DEFAULT_THROTTLE_RATES["user_merge"].
    """

    scope = "user_merge"
