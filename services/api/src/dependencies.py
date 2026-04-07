from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.database import get_db

settings = Settings()  # type: ignore[call-arg]


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> str:
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")
    # TODO: Validate Supabase JWT and return user ID
    raise NotImplementedError("Supabase JWT validation not yet implemented")


async def verify_internal_api_key(request: Request) -> None:
    api_key = request.headers.get("X-API-Key", "")
    if api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
