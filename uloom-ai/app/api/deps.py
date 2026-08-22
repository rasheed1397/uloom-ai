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
from app.repositories.user_repository import UserRepository
from app.services.ai_service.factory import get_chat_provider, get_embedding_provider
from app.services.auth_service import AuthService
from app.services.conversation_service import ConversationService
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


def get_auth_service(users: Annotated[UserRepository, Depends(get_user_repository)]) -> AuthService:
    return AuthService(users)


def get_vector_service(chunks: Annotated[ChunkRepository, Depends(get_chunk_repository)]) -> VectorService:
    return VectorService(chunks, get_embedding_provider())


def get_conversation_service(
    conversations: Annotated[ConversationRepository, Depends(get_conversation_repository)],
    messages: Annotated[MessageRepository, Depends(get_message_repository)],
    vector_service: Annotated[VectorService, Depends(get_vector_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConversationService:
    return ConversationService(conversations, messages, vector_service, get_chat_provider(), settings)


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
    if user is None:
        raise credentials_error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
