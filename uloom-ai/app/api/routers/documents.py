"""Resource: /documents, /documents/{id} (Detailed Design Sec.4, SRS FR-003)."""
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(_user: CurrentUser) -> dict[str, str]:
    # FR-003/FR-004: blocked on object storage backend decision (Detailed
    # Design Sec.6). Wire to DocumentService.upload_and_index once resolved.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get("")
async def list_documents(_user: CurrentUser) -> list[dict]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get("/{document_id}")
async def get_document(document_id: uuid.UUID, _user: CurrentUser) -> dict:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, _user: CurrentUser) -> None:
    # SRS Sec.10: delete must remove content, chunks, and embeddings within SLA.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
