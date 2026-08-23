"""Admin Service (SRS FR-009). Scoped to user and document administration
for v1 - AI provider credential rotation is deliberately not implemented
here: doing it safely needs a managed secret store (NFR-004), which this
codebase doesn't have yet, so bolting ad-hoc credential storage onto this
service would undermine that requirement rather than satisfy it.
"""
import uuid

from app.models.document import Document
from app.models.user import User, UserRole
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_repository import UserRepository
from app.services.document_service import DocumentService


class UserNotFoundError(Exception): ...


class DocumentNotFoundError(Exception): ...


class AdminService:
    def __init__(
        self,
        user_repository: UserRepository,
        document_repository: DocumentRepository,
        document_service: DocumentService,
    ) -> None:
        self._users = user_repository
        self._documents = document_repository
        self._document_service = document_service

    async def list_users(self) -> list[User]:
        return await self._users.list_all()

    async def update_user(
        self, user_id: uuid.UUID, role: UserRole | None, is_active: bool | None
    ) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        return user

    async def list_documents(self) -> list[Document]:
        return await self._documents.list_all()

    async def delete_document(self, document_id: uuid.UUID) -> None:
        document = await self._documents.get_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError(document_id)
        await self._document_service.delete(document)
