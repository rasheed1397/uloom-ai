import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository):
    async def create(self, document: Document) -> Document:
        self._session.add(document)
        await self._session.flush()
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return await self._session.get(Document, document_id)

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Document]:
        result = await self._session.execute(select(Document).where(Document.owner_id == owner_id))
        return list(result.scalars().all())

    async def list_all(self) -> list[Document]:
        result = await self._session.execute(select(Document))
        return list(result.scalars().all())

    async def list_older_than(self, cutoff: datetime) -> list[Document]:
        # Sec.10 retention sweep: targeted query rather than list_all() +
        # Python-side filtering, since this runs platform-wide across every
        # user's documents.
        result = await self._session.execute(select(Document).where(Document.created_at < cutoff))
        return list(result.scalars().all())

    async def delete(self, document: Document) -> None:
        await self._session.delete(document)
        await self._session.flush()

    async def commit(self) -> None:
        # Only DocumentRepository exposes this: DocumentService.create_upload
        # needs the row durably visible to *other* DB connections (a
        # concurrent GET /documents from the same browser session, not just
        # this one) before it returns, since the background task that runs
        # next can take real time (a live embedding call) - see
        # DocumentService.create_upload for the full explanation.
        await self._session.commit()
