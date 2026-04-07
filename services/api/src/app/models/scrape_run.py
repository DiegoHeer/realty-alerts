from datetime import UTC, datetime

from sqlalchemy import Index
from sqlmodel import Field, SQLModel

from app.enums import ScrapeRunStatus, Website


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"
    __table_args__ = (Index("idx_scrape_runs_website_started", "website", "started_at"),)

    id: int | None = Field(default=None, primary_key=True)
    website: Website
    started_at: datetime = Field(default_factory=_utcnow)
    finished_at: datetime | None = None
    status: ScrapeRunStatus = ScrapeRunStatus.RUNNING
    listings_found: int = 0
    listings_new: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None
