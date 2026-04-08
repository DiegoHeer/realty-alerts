from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_db
from app.dependencies import get_current_user
from app.enums import Website
from app.models.listing import Listing
from app.models.user import UserProfile
from app.schemas.listing import ListingRead

router = APIRouter(prefix="/listings", tags=["listings"])


@router.get("/", response_model=list[ListingRead])
async def list_listings(
    city: str | None = None,
    min_price: int | None = None,
    max_price: int | None = None,
    property_type: str | None = None,
    website: Website | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Listing]:
    query = select(Listing)

    if city:
        query = query.where(Listing.city == city)
    if property_type:
        query = query.where(Listing.property_type == property_type)
    if website:
        query = query.where(Listing.website == website)
    if min_price is not None:
        query = query.where(Listing.price_cents >= min_price)
    if max_price is not None:
        query = query.where(Listing.price_cents <= max_price)

    query = query.order_by(Listing.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{listing_id}", response_model=ListingRead)
async def get_listing(
    listing_id: int,
    _user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Listing:
    result = await db.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing
