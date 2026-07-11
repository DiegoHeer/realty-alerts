import json
from datetime import datetime

from ninja import Router
from ninja.errors import HttpError

from accounts.auth import JWTAuth
from accounts.models import UserPreferences
from accounts.schemas import NotificationsPrefIn, NotificationsPrefOut, SearchPrefIn, SearchPrefOut

me_router = Router(auth=JWTAuth())

SEARCH_MAX_BYTES = 4096


def _read_doc(value: dict, updated_at: datetime | None) -> tuple[dict | None, datetime | None]:
    return (value if updated_at is not None else None), updated_at


def _apply_lww(prefs: UserPreferences, field: str, ts_field: str, value: dict, incoming_ts: datetime) -> None:
    stored = getattr(prefs, ts_field)
    if stored is None or incoming_ts > stored:
        setattr(prefs, field, value)
        setattr(prefs, ts_field, incoming_ts)
        prefs.save(update_fields=[field, ts_field, "updated_at"])


@me_router.get("/preferences/search", response=SearchPrefOut)
def get_search_preferences(request):
    prefs = UserPreferences.objects.filter(user=request.user).first()
    if prefs is None:
        return {"search": None, "updated_at": None}
    value, updated_at = _read_doc(prefs.search, prefs.search_updated_at)
    return {"search": value, "updated_at": updated_at}


@me_router.put("/preferences/search", response=SearchPrefOut)
def put_search_preferences(request, payload: SearchPrefIn):
    # Reject oversized payloads before the LWW gate — fail fast on abusive
    # input regardless of whether the write would win. Measure compact bytes
    # so the cap matches what is actually stored.
    if len(json.dumps(payload.search, separators=(",", ":")).encode()) > SEARCH_MAX_BYTES:
        raise HttpError(422, "payload_too_large")
    prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
    _apply_lww(prefs, "search", "search_updated_at", payload.search, payload.updated_at)
    value, updated_at = _read_doc(prefs.search, prefs.search_updated_at)
    return {"search": value, "updated_at": updated_at}


@me_router.get("/preferences/notifications", response=NotificationsPrefOut)
def get_notification_preferences(request):
    prefs = UserPreferences.objects.filter(user=request.user).first()
    if prefs is None:
        return {"notifications": None, "updated_at": None}
    value, updated_at = _read_doc(prefs.notifications, prefs.notifications_updated_at)
    return {"notifications": value, "updated_at": updated_at}


@me_router.put("/preferences/notifications", response=NotificationsPrefOut)
def put_notification_preferences(request, payload: NotificationsPrefIn):
    prefs, _ = UserPreferences.objects.get_or_create(user=request.user)
    _apply_lww(prefs, "notifications", "notifications_updated_at", payload.notifications, payload.updated_at)
    value, updated_at = _read_doc(prefs.notifications, prefs.notifications_updated_at)
    return {"notifications": value, "updated_at": updated_at}
