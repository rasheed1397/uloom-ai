import uuid

import pytest
from fastapi import HTTPException

from app.api import deps
from app.core.config import Settings
from app.core.security import create_access_token
from app.models.user import User, UserRole


class FakeUserRepository:
    def __init__(self, users: dict[uuid.UUID, User]) -> None:
        self.users = users

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users.get(user_id)


def _make_user(role: UserRole = UserRole.STANDARD, is_active: bool = True) -> User:
    # is_active=True passed explicitly: User.is_active's default is applied
    # by SQLAlchemy at INSERT/flush time, not by the Python constructor, so
    # a bare User(...) would otherwise have is_active=None (falsy).
    return User(
        id=uuid.uuid4(), email="user@example.com", hashed_password="hashed", role=role, is_active=is_active
    )


def test_repository_wrapper_dependencies_construct_repositories():
    session = object()
    assert deps.get_user_repository(session)._session is session
    assert deps.get_document_repository(session)._session is session
    assert deps.get_chunk_repository(session)._session is session
    assert deps.get_conversation_repository(session)._session is session
    assert deps.get_message_repository(session)._session is session


def test_get_auth_service_wraps_repository():
    session = object()
    users = deps.get_user_repository(session)
    service = deps.get_auth_service(users, Settings())
    assert service._users is users


async def test_get_current_user_returns_user_for_valid_token():
    user = _make_user()
    repo = FakeUserRepository({user.id: user})
    token = create_access_token(subject=str(user.id), role=user.role.value)

    result = await deps.get_current_user(token=token, users=repo)

    assert result is user


async def test_get_current_user_rejects_missing_token():
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(token=None, users=FakeUserRepository({}))
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_garbage_token():
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(token="not-a-jwt", users=FakeUserRepository({}))
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_token_with_non_uuid_subject():
    token = create_access_token(subject="not-a-uuid", role="standard")
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(token=token, users=FakeUserRepository({}))
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_unknown_user():
    token = create_access_token(subject=str(uuid.uuid4()), role="standard")
    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(token=token, users=FakeUserRepository({}))
    assert exc_info.value.status_code == 401


async def test_get_current_user_rejects_disabled_user():
    user = _make_user(is_active=False)
    repo = FakeUserRepository({user.id: user})
    token = create_access_token(subject=str(user.id), role=user.role.value)

    with pytest.raises(HTTPException) as exc_info:
        await deps.get_current_user(token=token, users=repo)
    assert exc_info.value.status_code == 401


async def test_require_admin_allows_admin_user():
    admin = _make_user(role=UserRole.ADMIN)
    assert await deps.require_admin(admin) is admin


async def test_require_admin_rejects_standard_user():
    standard = _make_user(role=UserRole.STANDARD)
    with pytest.raises(HTTPException) as exc_info:
        await deps.require_admin(standard)
    assert exc_info.value.status_code == 403
