from datetime import datetime

from sqlalchemy import DateTime, Index
from sqlmodel import Field, SQLModel

from app.enums import ScrapeRunStatus, Website
from app.utils import utcnow


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"
    __table_args__ = (Index("idx_scrape_runs_website_started", "website", "started_at"),)

    id: int | None = Field(default=None, primary_key=True)
    website: Website
    started_at: datetime = Field(default_factory=utcnow, sa_type=DateTime(timezone=True))
    finished_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    status: ScrapeRunStatus = ScrapeRunStatus.RUNNING
    listings_found: int = 0
    listings_new: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None
