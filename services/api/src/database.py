from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    return create_async_engine(url, echo=False)


def get_session_factory(database_url: str | None = None):
    return async_sessionmaker(get_engine(database_url), class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
