from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_db
from app.dependencies import verify_internal_api_key
from app.enums import ScrapeRunStatus, Website
from app.models.listing import Listing
from app.utils import parse_price_cents
from app.models.scrape_run import ScrapeRun
from app.schemas.scrape_run import ScrapeResultSubmission, ScrapeRunRead

router = APIRouter(dependencies=[Depends(verify_internal_api_key)], tags=["internal"])


@router.get("/scrape-runs/{website}/last-successful", response_model=ScrapeRunRead | None)
async def get_last_successful_run(website: Website, db: AsyncSession = Depends(get_db)) -> ScrapeRun | None:
    result = await db.execute(
        select(ScrapeRun)
        .where(ScrapeRun.website == website, ScrapeRun.status == ScrapeRunStatus.SUCCESS)
        .order_by(ScrapeRun.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.post("/scrape-runs/{website}/results", response_model=ScrapeRunRead)
async def submit_scrape_results(
    website: Website,
    data: ScrapeResultSubmission,
    db: AsyncSession = Depends(get_db),
) -> ScrapeRun:
    duration = (data.finished_at - data.started_at).total_seconds()
    listings_new = 0

    # Upsert listings — insert new, skip existing (dedup by detail_url)
    new_listings: list[Listing] = []
    for listing_data in data.listings:
        result = await db.execute(select(Listing).where(Listing.detail_url == listing_data.detail_url))
        existing = result.scalar_one_or_none()
        if existing is None:
            listing = Listing(
                **listing_data.model_dump(),
                scraped_at=datetime.now(UTC),
                price_cents=parse_price_cents(listing_data.price),
            )
            db.add(listing)
            new_listings.append(listing)
            listings_new += 1

    # Create scrape run log
    run_status = ScrapeRunStatus.FAILED if data.error_message else ScrapeRunStatus.SUCCESS
    scrape_run = ScrapeRun(
        website=website,
        started_at=data.started_at,
        finished_at=data.finished_at,
        status=run_status,
        listings_found=len(data.listings),
        listings_new=listings_new,
        error_message=data.error_message,
        duration_seconds=duration,
    )
    db.add(scrape_run)
    await db.commit()
    await db.refresh(scrape_run)

    logger.info(f"Scrape run for {website}: {listings_new} new / {len(data.listings)} found in {duration:.1f}s")

    # Match new listings against user filters and send push notifications
    if new_listings:
        from app.matching.engine import find_matching_users
        from app.services.push import send_push_for_matches

        user_matches = await find_matching_users(new_listings, db)
        await send_push_for_matches(user_matches, db)

    return scrape_run


@router.get("/scrape-runs/active", response_model=list[ScrapeRunRead])
async def get_active_runs(db: AsyncSession = Depends(get_db)) -> list[ScrapeRun]:
    result = await db.execute(select(ScrapeRun).where(ScrapeRun.status == ScrapeRunStatus.RUNNING))
    return list(result.scalars().all())
