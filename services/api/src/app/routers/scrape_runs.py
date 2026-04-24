from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.scrape_run import ScrapeRun
from app.models.user import UserProfile
from app.schemas.scrape_run import ScrapeRunRead
from database import get_db
from dependencies import get_current_user
from enums import Website

router = APIRouter(prefix="/scrape-runs", tags=["scrape-runs"])


@router.get("/", response_model=list[ScrapeRunRead])
async def list_scrape_runs(
    website: Website | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScrapeRun]:
    query = select(ScrapeRun)
    if website:
        query = query.where(ScrapeRun.website == website)
    query = query.order_by(ScrapeRun.started_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())
