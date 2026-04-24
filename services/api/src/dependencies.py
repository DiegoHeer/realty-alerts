import hmac
import uuid

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.models.user import UserProfile
from database import get_db, get_settings


async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)) -> UserProfile:
    settings = get_settings()
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authorization token")

    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    supabase_id = uuid.UUID(payload["sub"])

    # Just-in-time user provisioning
    result = await db.execute(select(UserProfile).where(UserProfile.supabase_id == supabase_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = UserProfile(supabase_id=supabase_id, email=payload.get("email"))
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info(f"Created new user profile for {supabase_id}")

    return user


async def verify_internal_api_key(request: Request) -> None:
    settings = get_settings()
    api_key = request.headers.get("X-API-Key", "")
    if not hmac.compare_digest(api_key, settings.internal_api_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key")
