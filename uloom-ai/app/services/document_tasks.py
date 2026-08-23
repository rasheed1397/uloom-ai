"""Entry point for background document indexing (FastAPI BackgroundTasks).
Opens its own DB session rather than reusing the request's, so indexing
still completes correctly regardless of when the request's own session is
torn down.
"""
import uuid

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.services.ai_service.factory import get_embedding_provider
from app.services.document_service import DocumentService
from app.services.storage.factory import get_storage_backend


async def run_document_processing(document_id: uuid.UUID) -> None:
    settings = get_settings()
    async with SessionLocal() as session, session.begin():
        service = DocumentService(
            document_repository=DocumentRepository(session),
            chunk_repository=ChunkRepository(session),
            embedding_provider=get_embedding_provider(),
            storage=get_storage_backend(),
            allowed_mime_types=settings.allowed_upload_mime_types,
            max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
            chunk_token_size=settings.chunk_token_size,
        )
        await service.process(document_id)
