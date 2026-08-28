"""Async SQLAlchemy engine/session (SRS Sec.7: PostgreSQL + pgvector)."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()
engine = create_async_engine(_settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    # Explicit commit/rollback rather than `async with session.begin():` -
    # that context manager owns the transaction's lifecycle end-to-end, so a
    # service calling session.commit() mid-request (DocumentService.
    # create_upload, to make a row visible before a slow background task
    # runs) leaves it unable to exit cleanly ("Can't operate on closed
    # transaction inside context manager"). A plain try/except lets callers
    # commit early and keep using the session afterwards - SQLAlchemy opens
    # a fresh transaction automatically on the next statement.
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
