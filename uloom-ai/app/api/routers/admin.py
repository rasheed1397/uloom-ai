"""Resource: /admin/* (Detailed Design Sec.4, SRS FR-009). Admin-only."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AdminUser, get_admin_service
from app.core.config import Settings, get_settings
from app.schemas.admin import AdminUserOut, SettingsOut, UpdateUserRequest
from app.schemas.documents import DocumentOut
from app.services.admin_service import AdminService, DocumentNotFoundError, UserNotFoundError

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserOut])
async def list_users(
    _admin: AdminUser, admin_service: Annotated[AdminService, Depends(get_admin_service)]
) -> list[AdminUserOut]:
    users = await admin_service.list_users()
    return [AdminUserOut.model_validate(u) for u in users]


@router.patch("/users/{user_id}", response_model=AdminUserOut)
async def update_user(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    _admin: AdminUser,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> AdminUserOut:
    try:
        user = await admin_service.update_user(user_id, role=body.role, is_active=body.is_active)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from None
    return AdminUserOut.model_validate(user)


@router.get("/documents", response_model=list[DocumentOut])
async def list_all_documents(
    _admin: AdminUser, admin_service: Annotated[AdminService, Depends(get_admin_service)]
) -> list[DocumentOut]:
    documents = await admin_service.list_documents()
    return [DocumentOut.model_validate(d) for d in documents]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_any_document(
    document_id: uuid.UUID,
    _admin: AdminUser,
    admin_service: Annotated[AdminService, Depends(get_admin_service)],
) -> None:
    try:
        await admin_service.delete_document(document_id)
    except DocumentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from None


@router.get("/settings", response_model=SettingsOut)
async def get_settings_view(
    _admin: AdminUser, settings: Annotated[Settings, Depends(get_settings)]
) -> SettingsOut:
    return SettingsOut(
        retrieval_top_k=settings.retrieval_top_k,
        chunk_token_size=settings.chunk_token_size,
        similarity_threshold=settings.similarity_threshold,
    )


@router.patch("/settings")
async def update_settings_view(_admin: AdminUser) -> None:
    # Deliberately still not implemented: FR-009 wants these adjustable
    # "without a deployment", which means runtime-mutable persisted config,
    # not the startup-time Settings object used everywhere else in the app.
    # Doing that properly is a schema + read-path change across VectorService/
    # ConversationService, not a one-route fix - left as a follow-up rather
    # than half-implemented here.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
