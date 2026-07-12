from datetime import datetime

from ninja import Schema
from pydantic import AwareDatetime


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
