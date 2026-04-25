import hmac

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserProfile
from database import get_db, get_settings


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserProfile:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Authentication not implemented; tracked in follow-up PR",
    )


async def verify_internal_api_key(request: Request) -> None:
    settings = get_settings()
    api_key = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(api_key, settings.internal_api_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
