"""Document Service (Detailed Design Sec.5.2). SRS FR-003, FR-004.

Upload/parse/chunk/embed pipeline is stubbed pending the object-storage
backend decision (Detailed Design Sec.6, open item). The shape here fixes
the flow from Detailed Design Figure 3; fill in storage + parsing + chunking
+ AI Service calls when that decision lands.
"""
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.ai_service.interfaces import EmbeddingProvider


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._embeddings = embedding_provider

    async def upload_and_index(self, owner_id: str, filename: str, mime_type: str, content: bytes) -> None:
        raise NotImplementedError(
            "FR-003/FR-004: store file, parse, chunk, embed via self._embeddings, "
            "persist chunks. Blocked on object storage backend decision "
            "(Detailed Design Sec.6)."
        )
