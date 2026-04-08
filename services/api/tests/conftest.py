import os

# Set required environment variables before importing app modules
os.environ.setdefault("API_SUPABASE_JWT_SECRET", "test-jwt-secret")
os.environ.setdefault("API_INTERNAL_API_KEY", "test-api-key")

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_settings
from app.main import create_app


@pytest.fixture
def app():
    get_settings.cache_clear()
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
