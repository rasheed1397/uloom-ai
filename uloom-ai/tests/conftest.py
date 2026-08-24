import pytest
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionLocal
from app.main import app
from app.models.base import Base
from app.models.system_settings import SystemSettings

# Seeded once by migration 0003, not per-test data - reset to these known
# values rather than truncated, so SystemSettingsRepository.get() (which
# expects exactly one row, id=1) always has something to find, and every
# test starts from the same known settings regardless of test order.
_DEFAULT_RETRIEVAL_TOP_K = 5
_DEFAULT_CHUNK_TOKEN_SIZE = 512
_DEFAULT_SIMILARITY_THRESHOLD = 0.7


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
            if table.name != SystemSettings.__tablename__:
                await session.execute(table.delete())
        settings = await session.get(SystemSettings, 1)
        settings.retrieval_top_k = _DEFAULT_RETRIEVAL_TOP_K
        settings.chunk_token_size = _DEFAULT_CHUNK_TOKEN_SIZE
        settings.similarity_threshold = _DEFAULT_SIMILARITY_THRESHOLD
