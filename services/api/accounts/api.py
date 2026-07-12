import json
from datetime import datetime

from allauth.headless.contrib.ninja.security import jwt_token_auth
from django.db import transaction
from django.utils import timezone
from loguru import logger
from ninja import Router, Status
from ninja.errors import HttpError

from accounts.models import Favorite, UserPreferences
from accounts.mru import upsert_and_evict
from accounts.schemas import (
    FavoritePutIn,
    FavoritesMergeIn,
    FavoritesOut,
    NotificationsPrefIn,
    NotificationsPrefOut,
    SearchPrefIn,
    SearchPrefOut,
)
from scraping.models import Residence
from scraping.selectors import residence_summary_qs

me_router = Router(auth=jwt_token_auth)

SEARCH_MAX_BYTES = 4096
FAVORITES_CAP = 200


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


def _favorites_collection(user) -> dict:
    favorites = list(Favorite.objects.filter(user=user).order_by("-liked_at").values("residence_id", "liked_at"))
    residence_ids = [row["residence_id"] for row in favorites]
    residences = residence_summary_qs().in_bulk(residence_ids)
    items = [
        {"residence": residences[row["residence_id"]], "liked_at": row["liked_at"]}
        for row in favorites
        if row["residence_id"] in residences
    ]
    return {"items": items, "total": len(items)}


@me_router.get("/favorites", response=FavoritesOut)
def list_favorites(request):
    return _favorites_collection(request.user)


@me_router.post("/favorites/merge", response=FavoritesOut)
def merge_favorites(request, payload: FavoritesMergeIn):
    if len(payload.items) > FAVORITES_CAP:
        raise HttpError(422, "too_many_items")
    now = timezone.now()
    known_ids = set(
        Residence.objects.filter(id__in=[item.residence_id for item in payload.items]).values_list("id", flat=True)
    )
    skipped = 0
    with transaction.atomic():
        for item in payload.items:
            if item.residence_id not in known_ids:
                skipped += 1
                continue
            liked_at = min(item.liked_at, now)
            favorite, created = Favorite.objects.get_or_create(
                user=request.user, residence_id=item.residence_id, defaults={"liked_at": liked_at}
            )
            if not created and liked_at > favorite.liked_at:
                favorite.liked_at = liked_at
                favorite.save(update_fields=["liked_at"])
        stale_ids = list(
            Favorite.objects.filter(user=request.user)
            .order_by("-liked_at")
            .values_list("id", flat=True)[FAVORITES_CAP:]
        )
        if stale_ids:
            Favorite.objects.filter(id__in=stale_ids).delete()
    if skipped:
        logger.info("favorites merge skipped {} unknown residence ids for user {}", skipped, request.user.pk)
    return _favorites_collection(request.user)


@me_router.put("/favorites/{residence_id}", response={204: None})
def put_favorite(request, residence_id: int, payload: FavoritePutIn):
    residence = Residence.objects.filter(id=residence_id).first()
    if residence is None:
        raise HttpError(404, "residence_not_found")
    liked_at = payload.liked_at or timezone.now()
    upsert_and_evict(
        Favorite,
        user=request.user,
        residence=residence,
        timestamp_field="liked_at",
        timestamp=liked_at,
        cap=FAVORITES_CAP,
    )
    return Status(204, None)


@me_router.delete("/favorites/{residence_id}", response={204: None})
def delete_favorite(request, residence_id: int):
    Favorite.objects.filter(user=request.user, residence_id=residence_id).delete()
    return Status(204, None)
