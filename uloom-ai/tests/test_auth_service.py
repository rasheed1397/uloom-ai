import uuid

import pytest

from app.core.security import decode_access_token
from app.models.user import User, UserRole
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)


class FakeUserRepository:
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def create(self, user: User) -> User:
        user.id = uuid.uuid4()
        self.users[user.email] = user
        return user


@pytest.fixture
def auth_service() -> AuthService:
    return AuthService(FakeUserRepository())


async def test_register_creates_user_and_returns_token(auth_service: AuthService):
    user, token = await auth_service.register("new@example.com", "hunter2hunter2")

    assert user.email == "new@example.com"
    assert user.role == UserRole.STANDARD
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user.id)
    assert payload["role"] == "standard"


async def test_register_rejects_duplicate_email(auth_service: AuthService):
    await auth_service.register("dupe@example.com", "hunter2hunter2")

    with pytest.raises(EmailAlreadyRegisteredError):
        await auth_service.register("dupe@example.com", "anotherpassword")


async def test_login_returns_token_for_correct_password(auth_service: AuthService):
    registered, _ = await auth_service.register("login@example.com", "correcthorse")

    user, token = await auth_service.login("login@example.com", "correcthorse")

    assert user.id == registered.id
    assert decode_access_token(token) is not None


async def test_login_rejects_wrong_password(auth_service: AuthService):
    await auth_service.register("login2@example.com", "correcthorse")

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("login2@example.com", "wrongpassword")


async def test_login_rejects_unknown_email(auth_service: AuthService):
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("nobody@example.com", "whatever123")
