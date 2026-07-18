import json
from datetime import datetime

from allauth.headless.contrib.ninja.security import jwt_token_auth
from django.contrib.auth.models import AbstractBaseUser
from django.db import transaction
from django.utils import timezone
from loguru import logger
from ninja import Router, Status
from ninja.errors import HttpError

from accounts.models import Favorite, ResidenceView, UserPreferences
from accounts.mru import upsert_and_evict
from accounts.schemas import (
    AccountDeleteIn,
    FavoritePutIn,
    FavoritesMergeIn,
    FavoritesOut,
    NotificationsPrefIn,
    NotificationsPrefOut,
    RecentViewsOut,
    SearchPrefIn,
    SearchPrefOut,
)
from scraping.models import Residence
from scraping.selectors import residence_summary_qs
from scraping.throttling import UserMergeThrottle, UserWriteThrottle

me_router = Router(auth=jwt_token_auth)

SEARCH_MAX_BYTES = 4096
FAVORITES_CAP = 200
RECENT_VIEWS_CAP = 12


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


@me_router.put("/preferences/search", response=SearchPrefOut, throttle=[UserWriteThrottle()])
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


@me_router.put("/preferences/notifications", response=NotificationsPrefOut, throttle=[UserWriteThrottle()])
def put_notification_preferences(request, payload: NotificationsPrefIn):
    preferences, _ = UserPreferences.objects.get_or_create(user=request.user)
    _apply_last_write_wins(
        preferences, "notifications", "notifications_updated_at", payload.notifications, payload.updated_at
    )
    value, updated_at = _read_document(preferences.notifications, preferences.notifications_updated_at)
    return {"notifications": value, "updated_at": updated_at}


def _residence_collection(model, *, user: AbstractBaseUser, timestamp_field: str) -> dict:
    rows = list(model.objects.filter(user=user).order_by(f"-{timestamp_field}").values("residence_id", timestamp_field))
    residence_ids = [row["residence_id"] for row in rows]
    residences = residence_summary_qs().filter(latitude__isnull=False, longitude__isnull=False).in_bulk(residence_ids)
    items = [
        {"residence": residences[row["residence_id"]], timestamp_field: row[timestamp_field]}
        for row in rows
        if row["residence_id"] in residences
    ]
    return {"items": items, "total": len(items)}


@me_router.get("/favorites", response=FavoritesOut)
def list_favorites(request):
    return _residence_collection(Favorite, user=request.user, timestamp_field="liked_at")


@me_router.post("/favorites/merge", response=FavoritesOut, throttle=[UserMergeThrottle()])
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
    return _residence_collection(Favorite, user=request.user, timestamp_field="liked_at")


@me_router.put("/favorites/{residence_id}", response={204: None}, throttle=[UserWriteThrottle()])
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


@me_router.delete("/favorites/{residence_id}", response={204: None}, throttle=[UserWriteThrottle()])
def delete_favorite(request, residence_id: int):
    Favorite.objects.filter(user=request.user, residence_id=residence_id).delete()
    return Status(204, None)


@me_router.get("/recent-views", response=RecentViewsOut)
def list_recent_views(request):
    return _residence_collection(ResidenceView, user=request.user, timestamp_field="viewed_at")


@me_router.delete("/recent-views", response={204: None}, throttle=[UserWriteThrottle()])
def clear_recent_views(request):
    ResidenceView.objects.filter(user=request.user).delete()
    return Status(204, None)


@me_router.post("/recent-views/{residence_id}", response={204: None}, throttle=[UserWriteThrottle()])
def add_recent_view(request, residence_id: int):
    residence = Residence.objects.filter(id=residence_id).first()
    if residence is None:
        raise HttpError(404, "residence_not_found")
    upsert_and_evict(
        ResidenceView,
        user=request.user,
        residence=residence,
        timestamp_field="viewed_at",
        timestamp=timezone.now(),
        cap=RECENT_VIEWS_CAP,
    )
    return Status(204, None)


def _recently_reauthenticated(request) -> bool:
    """Whether the caller re-authenticated within ACCOUNT_REAUTHENTICATION_TIMEOUT (default 5 min).

    Reads the last authentication timestamp from the allauth session embedded in
    the caller's JWT. This is deliberately NOT allauth's own
    ``did_recently_authenticate``: under the headless JWT strategy ``jwt_token_auth``
    sets ``request.user`` but never attaches the session to ``request.session``, so
    that helper reads an empty session (always False for password users) AND
    short-circuits to True for users without a usable password — wrong in both
    directions. Reading ``methods[-1]["at"]`` from the token's own session works
    uniformly for password and social accounts.

    Token *refresh* does not bump this timestamp (only login / social login /
    reauthenticate do), so a long-lived app session goes stale and forces a fresh
    re-auth — which is the whole point. Relies on allauth internals, so it is
    covered by an end-to-end test; on any failure it fails closed (returns False,
    i.e. no deletion).
    """
    try:
        import time

        from allauth.account import app_settings as account_app_settings
        from allauth.account.internal.flows.login import AUTHENTICATION_METHODS_SESSION_KEY
        from allauth.headless.tokens.strategies.jwt.internal import get_token_session

        payload = request.auth
        if not isinstance(payload, dict):
            return False
        session = get_token_session(payload)
        if session is None:  # session flushed / logged out
            return False
        methods = session.get(AUTHENTICATION_METHODS_SESSION_KEY, [])
        if not methods:
            return False
        last_at = methods[-1].get("at")
        if last_at is None:
            return False
        return time.time() - last_at < account_app_settings.REAUTHENTICATION_TIMEOUT
    except Exception:
        logger.exception("reauth recency check failed; denying account deletion")
        return False


@me_router.delete("/account", response={204: None}, throttle=[UserWriteThrottle()])
def delete_account(request, payload: AccountDeleteIn):
    """Permanently delete the authenticated user's OWN account.

    Security: the account is taken solely from the JWT (``request.user``) — there is
    no user id in the path or body — so a caller can only ever delete themselves,
    never someone else's account. Deletion additionally requires FRESH proof of
    identity so a merely-unlocked device (with a long-lived session) can't wipe the
    account: either the correct current password (password accounts) or a
    re-authentication within the last few minutes (social accounts, which have no
    usable password and re-auth via a fresh provider-token login just before this
    call). A wrong-but-present password is reported distinctly so the app can say so.

    The delete cascades to preferences / favorites / recent-views and nulls the user
    FK on retained feedback (see models). Hard delete: irreversible by design.
    """
    user = request.user
    # Operator accounts must be removed via the admin, never self-served from the
    # app — this keeps a privileged account from being nuked off an unlocked phone.
    if user.is_staff or user.is_superuser:
        raise HttpError(403, "staff_account")

    password = (payload.password or "").strip()
    # check_password returns False for users with an unusable password (social-only),
    # so those correctly fall through to the recent-reauthentication check.
    reauthenticated = bool(password) and user.check_password(password)
    if not reauthenticated and not _recently_reauthenticated(request):
        raise HttpError(403, "password_incorrect" if password else "reauthentication_required")

    logger.info("self-service account deletion for user {} ({})", user.pk, user.email)
    with transaction.atomic():
        user.delete()
    return Status(204, None)
