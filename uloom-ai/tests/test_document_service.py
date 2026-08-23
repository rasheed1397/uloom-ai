import uuid
from unittest.mock import patch

import pytest

from app.models.chunk import Chunk
from app.models.document import Document, DocumentStatus
from app.services import document_service as document_service_module
from app.services.ai_service.dtos import EmbedRequest, EmbedResponse
from app.services.chunking import TextChunk
from app.services.document_parsing import ExtractedSegment, UnsupportedMimeTypeError
from app.services.document_service import DocumentService, FileTooLargeError

ALLOWED_MIME_TYPES = ("text/plain", "application/pdf")


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[uuid.UUID, Document] = {}
        self.deleted: list[Document] = []

    async def create(self, document: Document) -> Document:
        if document.id is None:
            document.id = uuid.uuid4()
        # Mirrors the DB: Document.status's default is applied by
        # SQLAlchemy at INSERT/flush time, not by the Python constructor.
        if document.status is None:
            document.status = DocumentStatus.UPLOADED
        self.documents[document.id] = document
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        return self.documents.get(document_id)

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Document]:
        return [d for d in self.documents.values() if d.owner_id == owner_id]

    async def delete(self, document: Document) -> None:
        self.deleted.append(document)
        self.documents.pop(document.id, None)


class FakeChunkRepository:
    def __init__(self) -> None:
        self.created: list[Chunk] = []

    async def bulk_create(self, chunks: list[Chunk]) -> list[Chunk]:
        self.created.extend(chunks)
        return chunks


class FakeEmbeddingProvider:
    def __init__(self, vectors: list[list[float]] | None = None) -> None:
        self.vectors = vectors or []
        self.last_request: EmbedRequest | None = None

    async def embed(self, request: EmbedRequest) -> EmbedResponse:
        self.last_request = request
        return EmbedResponse(vectors=self.vectors, dimension=len(self.vectors[0]) if self.vectors else 0)

    @property
    def capabilities(self):
        raise NotImplementedError


class FakeStorageBackend:
    def __init__(self, read_error: Exception | None = None) -> None:
        self.saved: dict[str, bytes] = {}
        self.deleted_keys: list[str] = []
        self.read_error = read_error

    async def save(self, key: str, content: bytes) -> None:
        self.saved[key] = content

    async def read(self, key: str) -> bytes:
        if self.read_error:
            raise self.read_error
        return self.saved[key]

    async def delete(self, key: str) -> None:
        self.deleted_keys.append(key)
        self.saved.pop(key, None)


def _make_service(
    documents: FakeDocumentRepository | None = None,
    chunks: FakeChunkRepository | None = None,
    embeddings: FakeEmbeddingProvider | None = None,
    storage: FakeStorageBackend | None = None,
    chunk_token_size: int = 512,
) -> DocumentService:
    return DocumentService(
        document_repository=documents or FakeDocumentRepository(),
        chunk_repository=chunks or FakeChunkRepository(),
        embedding_provider=embeddings or FakeEmbeddingProvider(),
        storage=storage or FakeStorageBackend(),
        allowed_mime_types=ALLOWED_MIME_TYPES,
        max_upload_size_bytes=1000,
        chunk_token_size=chunk_token_size,
    )


async def test_create_upload_rejects_unsupported_mime_type():
    documents = FakeDocumentRepository()
    service = _make_service(documents=documents)

    with pytest.raises(UnsupportedMimeTypeError):
        await service.create_upload(
            owner_id=uuid.uuid4(), filename="a.zip", mime_type="application/zip", content=b"data"
        )
    assert documents.documents == {}


async def test_create_upload_rejects_file_over_the_size_limit():
    service = DocumentService(
        document_repository=FakeDocumentRepository(),
        chunk_repository=FakeChunkRepository(),
        embedding_provider=FakeEmbeddingProvider(),
        storage=FakeStorageBackend(),
        allowed_mime_types=ALLOWED_MIME_TYPES,
        max_upload_size_bytes=10,
        chunk_token_size=512,
    )

    with pytest.raises(FileTooLargeError):
        await service.create_upload(
            owner_id=uuid.uuid4(), filename="a.txt", mime_type="text/plain", content=b"x" * 11
        )


async def test_create_upload_persists_document_and_raw_file():
    documents = FakeDocumentRepository()
    storage = FakeStorageBackend()
    service = _make_service(documents=documents, storage=storage)
    owner_id = uuid.uuid4()

    document = await service.create_upload(
        owner_id=owner_id, filename="a.txt", mime_type="text/plain", content=b"hello"
    )

    assert document.owner_id == owner_id
    assert document.filename == "a.txt"
    assert document.status == DocumentStatus.UPLOADED
    assert documents.documents[document.id] is document
    assert storage.saved[str(document.id)] == b"hello"


async def test_get_by_id_and_list_for_owner_delegate_to_repository():
    documents = FakeDocumentRepository()
    service = _make_service(documents=documents)
    owner_id = uuid.uuid4()
    mine = await service.create_upload(
        owner_id=owner_id, filename="a.txt", mime_type="text/plain", content=b"hi"
    )
    await service.create_upload(
        owner_id=uuid.uuid4(), filename="b.txt", mime_type="text/plain", content=b"hi"
    )

    assert await service.get_by_id(mine.id) is mine
    assert await service.list_for_owner(owner_id) == [mine]


async def test_process_is_a_noop_for_a_missing_document():
    chunks = FakeChunkRepository()
    service = _make_service(chunks=chunks)

    await service.process(uuid.uuid4())  # must not raise

    assert chunks.created == []


async def test_process_success_embeds_and_persists_chunks_then_marks_indexed():
    documents = FakeDocumentRepository()
    chunks = FakeChunkRepository()
    embeddings = FakeEmbeddingProvider(vectors=[[0.1, 0.2], [0.3, 0.4]])
    storage = FakeStorageBackend()
    service = _make_service(documents=documents, chunks=chunks, embeddings=embeddings, storage=storage)
    document = await service.create_upload(
        owner_id=uuid.uuid4(), filename="a.txt", mime_type="text/plain", content=b"hello world"
    )

    fake_segments = [ExtractedSegment(text="hello world", source_location={"offset": 0})]
    fake_text_chunks = [
        TextChunk(content="hello", token_count=1, source_location={"offset": 0}),
        TextChunk(content="world", token_count=1, source_location={"offset": 0, "token_offset": 1}),
    ]
    with (
        patch.object(document_service_module, "extract_text", return_value=fake_segments) as extract,
        patch.object(document_service_module, "chunk_segments", return_value=fake_text_chunks) as chunk,
    ):
        await service.process(document.id)

    extract.assert_called_once_with("text/plain", b"hello world")
    chunk.assert_called_once_with(fake_segments, service._chunk_token_size)
    assert document.status == DocumentStatus.INDEXED
    assert document.status_detail is None
    assert len(chunks.created) == 2
    assert chunks.created[0].content == "hello"
    assert chunks.created[0].embedding_vector == [0.1, 0.2]
    assert chunks.created[0].document_id == document.id
    assert chunks.created[1].content == "world"
    assert chunks.created[1].embedding_vector == [0.3, 0.4]
    assert embeddings.last_request == EmbedRequest(texts=["hello", "world"])


async def test_process_with_no_extractable_text_skips_embedding_but_still_indexes():
    documents = FakeDocumentRepository()
    chunks = FakeChunkRepository()
    embeddings = FakeEmbeddingProvider()
    service = _make_service(documents=documents, chunks=chunks, embeddings=embeddings)
    document = await service.create_upload(
        owner_id=uuid.uuid4(), filename="a.txt", mime_type="text/plain", content=b" "
    )

    with (
        patch.object(document_service_module, "extract_text", return_value=[]),
        patch.object(document_service_module, "chunk_segments", return_value=[]),
    ):
        await service.process(document.id)

    assert document.status == DocumentStatus.INDEXED
    assert chunks.created == []
    assert embeddings.last_request is None


async def test_process_marks_document_failed_with_reason_on_error():
    documents = FakeDocumentRepository()
    storage = FakeStorageBackend(read_error=RuntimeError("disk on fire"))
    service = _make_service(documents=documents, storage=storage)
    document = await service.create_upload(
        owner_id=uuid.uuid4(), filename="a.txt", mime_type="text/plain", content=b"hello"
    )

    await service.process(document.id)

    assert document.status == DocumentStatus.FAILED
    assert document.status_detail == "disk on fire"


async def test_delete_removes_storage_object_and_document_row():
    documents = FakeDocumentRepository()
    storage = FakeStorageBackend()
    service = _make_service(documents=documents, storage=storage)
    document = await service.create_upload(
        owner_id=uuid.uuid4(), filename="a.txt", mime_type="text/plain", content=b"hello"
    )

    await service.delete(document)

    assert storage.deleted_keys == [str(document.id)]
    assert documents.deleted == [document]
    assert document.id not in documents.documents
