from app.models.system_settings import SystemSettings
from app.repositories.base import BaseRepository

_SINGLETON_ID = 1


class SystemSettingsRepository(BaseRepository):
    async def get(self) -> SystemSettings:
        settings = await self._session.get(SystemSettings, _SINGLETON_ID)
        if settings is None:
            # Should only happen if the 0003 migration's seed row was
            # somehow removed; fail loudly rather than silently inventing
            # untracked defaults.
            raise RuntimeError("system_settings singleton row (id=1) is missing - was migration 0003 run?")
        return settings

    async def update(
        self,
        retrieval_top_k: int | None = None,
        chunk_token_size: int | None = None,
        similarity_threshold: float | None = None,
        retention_days: int | None = None,
    ) -> SystemSettings:
        settings = await self.get()
        if retrieval_top_k is not None:
            settings.retrieval_top_k = retrieval_top_k
        if chunk_token_size is not None:
            settings.chunk_token_size = chunk_token_size
        if similarity_threshold is not None:
            settings.similarity_threshold = similarity_threshold
        if retention_days is not None:
            settings.retention_days = retention_days
        await self._session.flush()
        return settings
