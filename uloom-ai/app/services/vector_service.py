"""Vector Service (Detailed Design Sec.5.3). SRS FR-005."""
import uuid

from app.models.chunk import Chunk
from app.repositories.chunk_repository import ChunkRepository
from app.services.ai_service.dtos import EmbedRequest
from app.services.ai_service.interfaces import EmbeddingProvider


class VectorService:
    def __init__(self, chunk_repository: ChunkRepository, embedding_provider: EmbeddingProvider) -> None:
        self._chunks = chunk_repository
        self._embeddings = embedding_provider

    async def search(
        self,
        query: str,
        owner_document_ids: list[uuid.UUID],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[Chunk]:
        embed_response = await self._embeddings.embed(EmbedRequest(texts=[query]))
        query_vector = embed_response.vectors[0]
        # Cosine distance (what pgvector orders/filters by) is the inverse of
        # cosine similarity (what SIMILARITY_THRESHOLD is expressed in):
        # distance 0 = identical, so a *higher* similarity floor means a
        # *lower* distance ceiling.
        max_distance = 1 - similarity_threshold if similarity_threshold is not None else None
        return await self._chunks.similarity_search(query_vector, owner_document_ids, top_k, max_distance)
