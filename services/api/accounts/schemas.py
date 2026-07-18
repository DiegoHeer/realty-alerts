from datetime import datetime

from ninja import Schema
from pydantic import AwareDatetime

from scraping.schemas import ResidenceSummaryOut


class SearchPrefOut(Schema):
    search: dict | None
    updated_at: datetime | None


class SearchPrefIn(Schema):
    search: dict
    updated_at: AwareDatetime


class NotificationsPrefOut(Schema):
    notifications: dict | None
    updated_at: datetime | None


class NotificationsPrefIn(Schema):
    notifications: dict
    updated_at: AwareDatetime


class FavoriteItemOut(Schema):
    residence: ResidenceSummaryOut
    liked_at: datetime


class FavoritesOut(Schema):
    items: list[FavoriteItemOut]
    total: int


class FavoritePutIn(Schema):
    liked_at: AwareDatetime | None = None


class FavoriteMergeItemIn(Schema):
    residence_id: int
    liked_at: AwareDatetime


class FavoritesMergeIn(Schema):
    items: list[FavoriteMergeItemIn]


class RecentViewItemOut(Schema):
    residence: ResidenceSummaryOut
    viewed_at: datetime


class RecentViewsOut(Schema):
    items: list[RecentViewItemOut]
    total: int


class AccountDeleteIn(Schema):
    # Optional because social accounts (no usable password) re-authenticate via a
    # fresh provider-token login rather than by supplying a password here. When a
    # password IS given it is verified against the current user (see delete_account).
    password: str | None = None
