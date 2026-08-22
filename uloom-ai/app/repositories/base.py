"""Repository base (Detailed Design Sec.6: Business Services depend on
repository interfaces, not SQLAlchemy models directly, to keep persistence
swappable)."""
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
