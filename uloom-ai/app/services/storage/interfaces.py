"""Object storage capability interface (Detailed Design Sec.5.2/6: "object
storage backend (location TBD)" resolved to local volume for v1, kept
swappable behind this interface for S3-compatible storage later, following
the same adapter-per-provider pattern as the AI Service - Sec.5.6)."""
from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, key: str, content: bytes) -> None: ...

    @abstractmethod
    async def read(self, key: str) -> bytes: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...


class StorageError(Exception):
    """Raised when a storage backend fails to save, read, or delete an object."""
