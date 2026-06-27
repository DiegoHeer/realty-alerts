from django.conf import settings
from loguru import logger


def _resolve_request_api_version(request) -> int:
    """Resolve the client's declared contract version from a raw request:
    `?api_version` wins, then the `X-API-Version` header, else legacy 1."""
    raw = request.GET.get("api_version")
    if raw is None:
        raw = request.headers.get("X-API-Version")
    if raw is None:
        return 1
    try:
        return int(raw)
    except TypeError, ValueError:
        return 1


class ApiVersioningMiddleware:
    """Telemetry + deprecation lifecycle for the versioned API. Logs the declared
    api_version and (telemetry-only) X-App-Version per /v1 request, and attaches
    RFC 8594 Deprecation/Sunset headers for versions configured in
    settings.API_VERSION_LIFECYCLE. Behavior never branches on X-App-Version."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/v1/"):
            return response
        api_version = _resolve_request_api_version(request)
        app_version = request.headers.get("X-App-Version")
        logger.info(
            "api request: version={} app_version={} path={}",
            api_version,
            app_version,
            request.path,
        )
        lifecycle = settings.API_VERSION_LIFECYCLE.get(api_version)
        if lifecycle:
            response.headers["Deprecation"] = lifecycle["deprecation"]
            response.headers["Sunset"] = lifecycle["sunset"]
        return response
