from datetime import datetime

from sqlmodel import Field, SQLModel

from app.enums import ScrapeRunStatus, Website


class ScrapeRun(SQLModel, table=True):
    __tablename__ = "scrape_runs"

    id: int | None = Field(default=None, primary_key=True)
    website: Website
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None
    status: ScrapeRunStatus = ScrapeRunStatus.RUNNING
    listings_found: int = 0
    listings_new: int = 0
    error_message: str | None = None
    duration_seconds: float | None = None
