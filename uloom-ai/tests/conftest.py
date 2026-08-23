import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionLocal
from app.main import app
from app.models.base import Base


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session


@pytest.fixture(autouse=True)
async def _clean_db():
    async with SessionLocal() as session, session.begin():
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
