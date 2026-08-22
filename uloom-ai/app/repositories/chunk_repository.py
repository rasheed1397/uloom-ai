import uuid

from sqlalchemy import select

from app.models.chunk import Chunk
from app.repositories.base import BaseRepository


class ChunkRepository(BaseRepository):
    async def bulk_create(self, chunks: list[Chunk]) -> list[Chunk]:
        self._session.add_all(chunks)
        await self._session.flush()
        return chunks

    async def similarity_search(
        self, query_vector: list[float], owner_document_ids: list[uuid.UUID], top_k: int
    ) -> list[Chunk]:
        # FR-005: scoped to documents the requester is authorized to access.
        # Scoping happens in the WHERE clause itself, not as a post-filter
        # (Detailed Design Sec.5.3), to avoid leaking unauthorized-doc existence.
        stmt = (
            select(Chunk)
            .where(Chunk.document_id.in_(owner_document_ids))
            .order_by(Chunk.embedding_vector.cosine_distance(query_vector))
            .limit(top_k)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
