import uuid

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.filter import UserFilter
from app.models.listing import Listing


async def find_matching_users(listings: list[Listing], db: AsyncSession) -> dict[uuid.UUID, list[Listing]]:
    """Match new listings against all active user filters.

    Returns a dict of user_id -> list of matching listings.
    """
    if not listings:
        return {}

    result = await db.execute(select(UserFilter).where(UserFilter.is_active.is_(True)))
    active_filters = result.scalars().all()

    matches: dict[uuid.UUID, list[Listing]] = {}

    for user_filter in active_filters:
        for listing in listings:
            if _listing_matches_filter(listing, user_filter):
                matches.setdefault(user_filter.user_id, []).append(listing)

    total_matches = sum(len(v) for v in matches.values())
    logger.info(f"Matching: {total_matches} matches across {len(matches)} users for {len(listings)} new listings")
    return matches


def _listing_matches_filter(listing: Listing, f: UserFilter) -> bool:
    if f.city and listing.city.lower() != f.city.lower():
        return False
    if f.property_type and listing.property_type and listing.property_type.lower() != f.property_type.lower():
        return False
    if f.websites and listing.website not in f.websites:
        return False
    if f.min_bedrooms is not None and listing.bedrooms is not None and listing.bedrooms < f.min_bedrooms:
        return False
    if f.min_area_sqm is not None and listing.area_sqm is not None and listing.area_sqm < f.min_area_sqm:
        return False

    # Price comparison: try numeric extraction for min/max price filtering
    listing_price = _extract_numeric_price(listing.price)
    if listing_price is not None:
        if f.min_price is not None and listing_price < f.min_price:
            return False
        if f.max_price is not None and listing_price > f.max_price:
            return False

    return True


def _extract_numeric_price(price_str: str) -> int | None:
    """Extract numeric value from price strings like '€ 350.000 k.k.' or '1.250'."""
    cleaned = price_str.replace("€", "").replace("k.k.", "").replace("v.o.n.", "").replace(" ", "").strip()
    cleaned = cleaned.replace(".", "").replace(",", "")
    try:
        return int(cleaned)
    except ValueError:
        return None
