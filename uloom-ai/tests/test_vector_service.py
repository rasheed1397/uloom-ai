import uuid

import pytest

from app.models.chunk import Chunk
from app.services.ai_service.dtos import EmbedRequest, EmbedResponse
from app.services.vector_service import VectorService


class FakeEmbeddingProvider:
    def __init__(self, vector: list[float]) -> None:
        self.vector = vector
        self.last_request: EmbedRequest | None = None

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        self.last_request = request
        return EmbedResponse(vectors=[self.vector], dimension=len(self.vector))

    @property
    def capabilities(self):
        raise NotImplementedError


class FakeChunkRepository:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.last_call: tuple[list[float], list[uuid.UUID], int, float | None] | None = None

    async def similarity_search(
        self,
        query_vector: list[float],
        owner_document_ids: list[uuid.UUID],
        top_k: int,
        max_distance: float | None = None,
    ) -> list[Chunk]:
        self.last_call = (query_vector, owner_document_ids, top_k, max_distance)
        return self.chunks[:top_k]


async def test_search_embeds_query_and_delegates_to_repository():
    document_id = uuid.uuid4()
    chunk = Chunk(document_id=document_id, content="hello world", token_count=2, source_location={})
    embeddings = FakeEmbeddingProvider(vector=[0.1, 0.2, 0.3])
    chunks_repo = FakeChunkRepository([chunk])
    service = VectorService(chunks_repo, embeddings)

    result = await service.search("hello?", owner_document_ids=[document_id], top_k=5)

    assert result == [chunk]
    assert embeddings.last_request == EmbedRequest(texts=["hello?"])
    assert chunks_repo.last_call == ([0.1, 0.2, 0.3], [document_id], 5, None)


async def test_search_converts_similarity_threshold_to_max_cosine_distance():
    document_id = uuid.uuid4()
    embeddings = FakeEmbeddingProvider(vector=[0.1, 0.2, 0.3])
    chunks_repo = FakeChunkRepository([])
    service = VectorService(chunks_repo, embeddings)

    await service.search(
        "hello?", owner_document_ids=[document_id], top_k=5, similarity_threshold=0.7
    )

    assert chunks_repo.last_call is not None
    max_distance = chunks_repo.last_call[3]
    assert max_distance == pytest.approx(0.3)
