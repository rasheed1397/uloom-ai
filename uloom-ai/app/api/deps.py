"""Shared FastAPI dependencies: DB session, auth, and service wiring.

Role checks are enforced here via dependency injection rather than scattered
per-route (Detailed Design Sec.5.1 key design point).
"""
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.repositories.user_repository import UserRepository
from app.services.admin_service import AdminService
from app.services.ai_service.factory import get_chat_provider, get_embedding_provider
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.services.storage.factory import get_storage_backend
from app.services.vector_service import VectorService

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_user_repository(session: SessionDep) -> UserRepository:
    return UserRepository(session)


def get_document_repository(session: SessionDep) -> DocumentRepository:
    return DocumentRepository(session)


def get_chunk_repository(session: SessionDep) -> ChunkRepository:
    return ChunkRepository(session)


def get_conversation_repository(session: SessionDep) -> ConversationRepository:
    return ConversationRepository(session)


def get_message_repository(session: SessionDep) -> MessageRepository:
    return MessageRepository(session)


def get_system_settings_repository(session: SessionDep) -> SystemSettingsRepository:
    return SystemSettingsRepository(session)


async def get_effective_settings(
    settings: Annotated[Settings, Depends(get_settings)],
    system_settings: Annotated[SystemSettingsRepository, Depends(get_system_settings_repository)],
) -> Settings:
    """FR-009: retrieval_top_k/chunk_token_size/similarity_threshold are
    admin-adjustable at runtime (PATCH /admin/settings) without a
    deployment, so - unlike the rest of Settings, which is fixed at process
    startup from the environment - these three are re-read from the DB on
    every request. Settings.model_copy keeps everything else (secrets,
    provider config, storage paths) exactly as the static env-loaded
    values.
    """
    db_settings = await system_settings.get()
    return settings.model_copy(
        update={
            "retrieval_top_k": db_settings.retrieval_top_k,
            "chunk_token_size": db_settings.chunk_token_size,
            "similarity_threshold": db_settings.similarity_threshold,
        }
    )


def get_auth_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    return AuthService(users, admin_bootstrap_emails=settings.admin_bootstrap_emails)


def get_vector_service(chunks: Annotated[ChunkRepository, Depends(get_chunk_repository)]) -> VectorService:
    return VectorService(chunks, get_embedding_provider())


def get_conversation_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> ConversationService:
    return ConversationService(conversations, messages, vector_service, get_chat_provider(), settings)


def get_document_service(
    documents: Annotated[DocumentRepository, Depends(get_document_repository)],
    chunks: Annotated[ChunkRepository, Depends(get_chunk_repository)],
    settings: Annotated[Settings, Depends(get_effective_settings)],
) -> DocumentService:
    return DocumentService(
        document_repository=documents,
        chunk_repository=chunks,
        embedding_provider=get_embedding_provider(),
        storage=get_storage_backend(),
        allowed_mime_types=settings.allowed_upload_mime_types,
        max_upload_size_bytes=settings.max_upload_size_mb * 1024 * 1024,
        chunk_token_size=settings.chunk_token_size,
    )


def get_admin_service(
    users: Annotated[UserRepository, Depends(get_user_repository)],
    documents: Annotated[DocumentRepository, Depends(get_document_repository)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
    system_settings: Annotated[SystemSettingsRepository, Depends(get_system_settings_repository)],
) -> AdminService:
    return AdminService(users, documents, document_service, system_settings)


async def get_current_user(
    token: Annotated[str | None, Depends(_oauth2_scheme)],
    users: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise credentials_error
    try:
        user_id = uuid.UUID(payload["sub"])
    except ValueError:
        raise credentials_error from None
    user = await users.get_by_id(user_id)
    if user is None or not user.is_active:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
