import json
from datetime import datetime

from allauth.headless.contrib.ninja.security import jwt_token_auth
from ninja import Router
from ninja.errors import HttpError

from accounts.models import UserPreferences
from accounts.schemas import NotificationsPrefIn, NotificationsPrefOut, SearchPrefIn, SearchPrefOut

me_router = Router(auth=jwt_token_auth)

SEARCH_MAX_BYTES = 4096


def _read_document(value: dict, updated_at: datetime | None) -> tuple[dict | None, datetime | None]:
    return (value if updated_at is not None else None), updated_at


def _apply_last_write_wins(
    preferences: UserPreferences, field: str, timestamp_field: str, value: dict, incoming_timestamp: datetime
) -> None:
    stored = getattr(preferences, timestamp_field)
    if stored is None or incoming_timestamp > stored:
        setattr(preferences, field, value)
        setattr(preferences, timestamp_field, incoming_timestamp)
        preferences.save(update_fields=[field, timestamp_field, "updated_at"])


@me_router.get("/preferences/search", response=SearchPrefOut)
def get_search_preferences(request):
    preferences = UserPreferences.objects.filter(user=request.user).first()
    if preferences is None:
        return {"search": None, "updated_at": None}
    value, updated_at = _read_document(preferences.search, preferences.search_updated_at)
    return {"search": value, "updated_at": updated_at}


@me_router.put("/preferences/search", response=SearchPrefOut)
def put_search_preferences(request, payload: SearchPrefIn):
    # Reject oversized payloads before the last-write-wins gate — fail fast on
    # abusive input regardless of whether the write would win. Measure compact
    # bytes so the cap matches what is actually stored.
    if len(json.dumps(payload.search, separators=(",", ":")).encode()) > SEARCH_MAX_BYTES:
        raise HttpError(422, "payload_too_large")
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    _apply_last_write_wins(preferences, "search", "search_updated_at", payload.search, payload.updated_at)
    value, updated_at = _read_document(preferences.search, preferences.search_updated_at)
    return {"search": value, "updated_at": updated_at}


@me_router.get("/preferences/notifications", response=NotificationsPrefOut)
def get_notification_preferences(request):
    preferences = UserPreferences.objects.filter(user=request.user).first()
    if preferences is None:
        return {"notifications": None, "updated_at": None}
    value, updated_at = _read_document(preferences.notifications, preferences.notifications_updated_at)
    return {"notifications": value, "updated_at": updated_at}


@me_router.put("/preferences/notifications", response=NotificationsPrefOut)
def put_notification_preferences(request, payload: NotificationsPrefIn):
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    _apply_last_write_wins(
        preferences, "notifications", "notifications_updated_at", payload.notifications, payload.updated_at
    )
    value, updated_at = _read_document(preferences.notifications, preferences.notifications_updated_at)
    return {"notifications": value, "updated_at": updated_at}
