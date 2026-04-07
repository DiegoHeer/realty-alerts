from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database import get_db
from app.dependencies import get_current_user
from app.models.filter import UserFilter
from app.models.user import UserProfile
from app.schemas.filter import FilterCreate, FilterRead, FilterUpdate

router = APIRouter(prefix="/filters", tags=["filters"])


@router.get("/", response_model=list[FilterRead])
async def list_filters(
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserFilter]:
    query = select(UserFilter).where(UserFilter.user_id == user.id).order_by(UserFilter.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/", response_model=FilterRead, status_code=status.HTTP_201_CREATED)
async def create_filter(
    data: FilterCreate,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFilter:
    user_filter = UserFilter(**data.model_dump(), user_id=user.id)
    db.add(user_filter)
    await db.commit()
    await db.refresh(user_filter)
    return user_filter


@router.get("/{filter_id}", response_model=FilterRead)
async def get_filter(
    filter_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFilter:
    result = await db.execute(select(UserFilter).where(UserFilter.id == filter_id, UserFilter.user_id == user.id))
    user_filter = result.scalar_one_or_none()
    if user_filter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter not found")
    return user_filter


@router.patch("/{filter_id}", response_model=FilterRead)
async def update_filter(
    filter_id: int,
    data: FilterUpdate,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFilter:
    result = await db.execute(select(UserFilter).where(UserFilter.id == filter_id, UserFilter.user_id == user.id))
    user_filter = result.scalar_one_or_none()
    if user_filter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user_filter, key, value)
    user_filter.updated_at = datetime.now(UTC)
    db.add(user_filter)
    await db.commit()
    await db.refresh(user_filter)
    return user_filter


@router.delete("/{filter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_filter(
    filter_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(UserFilter).where(UserFilter.id == filter_id, UserFilter.user_id == user.id))
    user_filter = result.scalar_one_or_none()
    if user_filter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter not found")
    await db.delete(user_filter)
    await db.commit()


@router.post("/{filter_id}/toggle", response_model=FilterRead)
async def toggle_filter(
    filter_id: int,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserFilter:
    result = await db.execute(select(UserFilter).where(UserFilter.id == filter_id, UserFilter.user_id == user.id))
    user_filter = result.scalar_one_or_none()
    if user_filter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter not found")
    user_filter.is_active = not user_filter.is_active
    user_filter.updated_at = datetime.now(UTC)
    db.add(user_filter)
    await db.commit()
    await db.refresh(user_filter)
    return user_filter
