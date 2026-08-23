"""Document Service (Detailed Design Sec.5.2). SRS FR-003, FR-004.

Upload returns as soon as the Document row and raw file are persisted
(status=UPLOADED); parsing/chunking/embedding happens afterward via
`process()`, run from a background task so the API layer can return 202
immediately (Detailed Design Sec.5.2 key design point).
"""
import logging
import uuid

from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.ai_service.dtos import EmbedRequest
from app.services.ai_service.interfaces import EmbeddingProvider
from app.services.chunking import chunk_segments
from app.services.document_parsing import UnsupportedMimeTypeError, extract_text
from app.services.storage.interfaces import StorageBackend

logger = logging.getLogger(__name__)


class FileTooLargeError(Exception): ...


class DocumentService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: ChunkRepository,
        embedding_provider: EmbeddingProvider,
        storage: StorageBackend,
        allowed_mime_types: tuple[str, ...],
        max_upload_size_bytes: int,
        chunk_token_size: int,
    ) -> None:
        self._documents = document_repository
        self._chunks = chunk_repository
        self._embeddings = embedding_provider
        self._storage = storage
        self._allowed_mime_types = allowed_mime_types
        self._max_upload_size_bytes = max_upload_size_bytes
        self._chunk_token_size = chunk_token_size

    async def create_upload(
        self, owner_id: uuid.UUID, filename: str, mime_type: str, content: bytes
    ) -> Document:
        if mime_type not in self._allowed_mime_types:
            raise UnsupportedMimeTypeError(mime_type)
        if len(content) > self._max_upload_size_bytes:
            raise FileTooLargeError(len(content))

        document = await self._documents.create(
            Document(owner_id=owner_id, filename=filename, mime_type=mime_type)
        )
        await self._storage.save(_storage_key(document.id), content)
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return await self._documents.get_by_id(document_id)

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Document]:
        return await self._documents.list_for_owner(owner_id)

    async def process(self, document_id: uuid.UUID) -> None:
        """Parse, chunk, and embed an uploaded document. Any failure marks the
        document FAILED with a visible reason rather than leaving it stuck in
        PROCESSING (SRS Sec.9 degraded-mode handling). Called as a background
        task on the same request-scoped session as create_upload() (see the
        upload_document router) - it all lands in one transaction, so status
        transitions from UPLOADED straight to INDEXED/FAILED; PROCESSING is
        not separately observable, in exchange for atomicity without a task
        queue.
        """
        document = await self._documents.get_by_id(document_id)
        if document is None:
            logger.warning("process() called for missing document %s", document_id)
            return

        document.status = DocumentStatus.PROCESSING

        try:
            raw = await self._storage.read(_storage_key(document.id))
            segments = extract_text(document.mime_type, raw)
            text_chunks = chunk_segments(segments, self._chunk_token_size)
            if text_chunks:
                embed_response = await self._embeddings.embed(
                    EmbedRequest(texts=[c.content for c in text_chunks])
                )
                chunks = [
                    Chunk(
                        document_id=document.id,
                        content=text_chunk.content,
                        token_count=text_chunk.token_count,
                        embedding_vector=vector,
                        source_location=text_chunk.source_location,
                    )
                    for text_chunk, vector in zip(text_chunks, embed_response.vectors, strict=True)
                ]
                await self._chunks.bulk_create(chunks)
            document.status = DocumentStatus.INDEXED
        except Exception as exc:
            # Broad by design: any parsing/chunking/embedding failure must
            # land as a visible FAILED status (Sec.9), not an unhandled
            # exception lost inside a background task.
            logger.exception("Indexing failed for document %s", document_id)
            document.status = DocumentStatus.FAILED
            document.status_detail = str(exc)

    async def delete(self, document: Document) -> None:
        await self._storage.delete(_storage_key(document.id))
        await self._documents.delete(document)


def _storage_key(document_id: uuid.UUID) -> str:
    return f"{document_id}"
