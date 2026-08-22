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
        self, query: str, owner_document_ids: list[uuid.UUID], top_k: int
    ) -> list[Chunk]:
        embed_response = await self._embeddings.embed(EmbedRequest(texts=[query]))
        query_vector = embed_response.vectors[0]
        return await self._chunks.similarity_search(query_vector, owner_document_ids, top_k)
