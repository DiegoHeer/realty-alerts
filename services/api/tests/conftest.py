import pytest
from ninja.testing import TestClient

from scraping.api import api


@pytest.fixture
def client() -> TestClient:
    return TestClient(api)
