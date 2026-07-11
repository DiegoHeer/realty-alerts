from datetime import datetime

from ninja import Schema


class SearchPrefOut(Schema):
    search: dict | None
    updated_at: datetime | None
