"""Resource: /documents, /documents/{id} (Detailed Design Sec.4, SRS FR-003)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, get_document_service
from app.models.document import Document
from app.models.user import UserRole
from app.schemas.documents import DocumentOut
from app.services.document_parsing import UnsupportedMimeTypeError
from app.services.document_service import DocumentService, FileTooLargeError

router = APIRouter(prefix="/documents", tags=["documents"])


def _authorize(document: Document | None, user_id: uuid.UUID, role: UserRole) -> Document:
    # 404 rather than 403 for a document that exists but isn't yours, so the
    # response doesn't reveal whether the ID exists (Sec.10 authorization
    # scoping principle, same rationale as ChunkRepository.similarity_search).
    if document is None or (document.owner_id != user_id and role != UserRole.ADMIN):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=DocumentOut)
async def upload_document(
    user: CurrentUser,
    background_tasks: BackgroundTasks,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    file: UploadFile,
) -> DocumentOut:
    content = await file.read()
    try:
        document = await document_service.create_upload(
            owner_id=user.id,
            filename=file.filename or "untitled",
            mime_type=file.content_type or "application/octet-stream",
            content=content,
        )
    except UnsupportedMimeTypeError:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported file type"
        ) from None
    except FileTooLargeError:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File exceeds the size limit"
        ) from None

    # Reuses this request's DocumentService/session rather than opening a new
    # one: FastAPI runs background tasks *before* a yield-dependency's
    # post-yield code (get_session's commit), specifically so the same
    # session can be reused this way. A separate session here would race the
    # request's own commit and fail to see the row it just inserted.
    background_tasks.add_task(document_service.process, document.id)
    return DocumentOut.model_validate(document)


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    user: CurrentUser, document_service: Annotated[DocumentService, Depends(get_document_service)]
) -> list[DocumentOut]:
    documents = await document_service.list_for_owner(user.id)
    return [DocumentOut.model_validate(d) for d in documents]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> DocumentOut:
    document = await document_service.get_by_id(document_id)
    document = _authorize(document, user.id, user.role)
    return DocumentOut.model_validate(document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> None:
    # SRS Sec.10: delete must remove content, chunks, and embeddings within SLA.
    document = await document_service.get_by_id(document_id)
    document = _authorize(document, user.id, user.role)
    await document_service.delete(document)
