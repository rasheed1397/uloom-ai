"""Local filesystem storage backend (v1 default per Detailed Design Sec.6).

File I/O here is synchronous. Every caller in this codebase invokes it from a
background task (Document Service indexing), never from the request path, so
blocking the event loop briefly is an accepted tradeoff against adding an
async file I/O dependency for a single-writer use case at v1's scale.
"""
from pathlib import Path

from app.services.storage.interfaces import StorageBackend, StorageError


class LocalStorageBackend(StorageBackend):
    def __init__(self, base_path: str) -> None:
        self._base_path = Path(base_path)

    def _resolve(self, key: str) -> Path:
        path = (self._base_path / key).resolve()
        if self._base_path.resolve() not in path.parents and path != self._base_path.resolve():
            raise StorageError(f"Refusing to access path outside storage root: {key!r}")
        return path

    async def save(self, key: str, content: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    async def read(self, key: str) -> bytes:
        path = self._resolve(key)
        try:
            return path.read_bytes()
        except OSError as exc:
            raise StorageError(f"Could not read {key!r}: {exc}") from exc

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)
