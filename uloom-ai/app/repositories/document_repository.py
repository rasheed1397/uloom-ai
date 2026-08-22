import uuid

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
