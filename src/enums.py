from enum import StrEnum


class Websites(StrEnum):
    FUNDA = "www.funda.nl"


class QueryResultORMStatus(StrEnum):
    NEW = "new"
    UPDATED = "updated"
    NOTIFIED = "notified"

    @classmethod
    def choices(cls) -> list[tuple[str, str]]:
        return [(item.name, item.value) for item in list(cls)]

    @classmethod
    def values(cls) -> list[str]:
        return [item.value for item in list(cls)]
