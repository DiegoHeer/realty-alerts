from enum import StrEnum


class Website(StrEnum):
    FUNDA = "funda"
    PARARIUS = "pararius"
    VASTGOED_NL = "vastgoed_nl"


class ListingStatus(StrEnum):
    NEW = "new"
    SALE_PENDING = "sale_pending"
    SOLD = "sold"


class ScrapeMode(StrEnum):
    LIST = "list"
    DETAIL = "detail"


class DetailResultStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
