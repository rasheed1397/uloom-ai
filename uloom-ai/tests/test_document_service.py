import pytest

from app.services.document_service import DocumentService


async def test_upload_and_index_is_not_yet_implemented():
    service = DocumentService(document_repository=None, chunk_repository=None, embedding_provider=None)
    with pytest.raises(NotImplementedError):
        await service.upload_and_index(
            owner_id="owner-1", filename="doc.pdf", mime_type="application/pdf", content=b"data"
        )
