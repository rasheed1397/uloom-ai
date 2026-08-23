"""Config-driven storage backend selection, mirroring the AI Service factory
(Detailed Design Sec.5.6, practice #3)."""
from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.interfaces import StorageBackend
from app.services.storage.local_backend import LocalStorageBackend


@lru_cache
def get_storage_backend() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorageBackend(base_path=settings.document_storage_path)
    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.storage_backend!r}")
