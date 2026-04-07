from datetime import datetime

from sqlmodel import SQLModel

from app.enums import ScrapeRunStatus, Website
from app.schemas.listing import ListingCreate


class ScrapeRunRead(SQLModel):
    id: int
    website: Website
    started_at: datetime
    finished_at: datetime | None
    status: ScrapeRunStatus
    listings_found: int
    listings_new: int
    error_message: str | None
    duration_seconds: float | None


class ScrapeResultSubmission(SQLModel):
    listings: list[ListingCreate]
    started_at: datetime
    finished_at: datetime
    error_message: str | None = None
