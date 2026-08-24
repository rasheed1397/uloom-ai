"""Document Service (Detailed Design Sec.5.2). SRS FR-003, FR-004.

Upload returns as soon as the Document row and raw file are persisted
(status=UPLOADED) - `create_upload` commits explicitly before returning, so
the row is durably visible immediately, not just once processing finishes
(see the comment there). Parsing/chunking/embedding happens afterward via
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
        # Committed here, explicitly, rather than waiting for the ambient
        # per-request commit (app.core.db.get_session): FastAPI runs
        # background tasks *before* a yield-dependency's post-yield code, so
        # without this the row stays invisible to every other DB connection
        # - including a GET /documents from the same browser session right
        # after this response - until process() finishes below, which can
        # take real time (a live embedding call). The frontend polling
        # /uploading UI assumes the row exists the moment this returns.
        await self._documents.commit()
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
        upload_document router), but *after* create_upload's own explicit
        commit - so this runs in its own, second transaction, committed when
        the request's session teardown runs (after this background task
        finishes, per FastAPI's execution order). Status transitions from
        UPLOADED to PROCESSING to INDEXED/FAILED within that one transaction,
        so PROCESSING itself is still not separately observable to another
        connection - only the initial UPLOADED row's visibility was the bug,
        not this part.
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
