from datetime import datetime

from ninja import Schema


class SearchPrefOut(Schema):
    search: dict | None
    updated_at: datetime | None


class SearchPrefIn(Schema):
    search: dict
    updated_at: datetime
