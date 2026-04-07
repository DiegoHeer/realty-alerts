from enum import StrEnum


class Website(StrEnum):
    FUNDA = "funda"
    PARARIUS = "pararius"
    VASTGOED_NL = "vastgoed_nl"


class ScrapeRunStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ListingStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
