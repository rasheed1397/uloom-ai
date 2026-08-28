import uuid
from unittest.mock import patch

from app.core import bootstrap
from app.core.config import Settings
from app.core.security import verify_password
from app.models.user import User, UserRole


class FakeUserRepository:
    def __init__(self, users: dict[str, User] | None = None) -> None:
        self.users = users or {}
        self.created: list[User] = []

    async def get_by_email(self, email: str) -> User | None:
        return self.users.get(email)

    async def create(self, user: User) -> User:
        user.id = uuid.uuid4()
        self.users[user.email] = user
        self.created.append(user)
        return user


def _settings(**overrides) -> Settings:
    return Settings(**overrides)


async def test_ensure_default_admin_does_nothing_when_unconfigured():
    users = FakeUserRepository()

    with patch.object(bootstrap, "get_settings", return_value=_settings()):
        await bootstrap.ensure_default_admin(users)

    assert users.created == []


async def test_ensure_default_admin_does_nothing_when_only_email_set():
    users = FakeUserRepository()
    settings = _settings(default_admin_email="admin@example.com")

    with patch.object(bootstrap, "get_settings", return_value=settings):
        await bootstrap.ensure_default_admin(users)

    assert users.created == []


async def test_ensure_default_admin_creates_admin_when_configured():
    users = FakeUserRepository()
    settings = _settings(
        default_admin_email="admin@example.com", default_admin_password="hunter2hunter2"
    )

    with patch.object(bootstrap, "get_settings", return_value=settings):
        await bootstrap.ensure_default_admin(users)

    assert len(users.created) == 1
    created = users.created[0]
    assert created.email == "admin@example.com"
    assert created.role == UserRole.ADMIN
    assert verify_password("hunter2hunter2", created.hashed_password)


async def test_ensure_default_admin_is_idempotent():
    existing = User(
        id=uuid.uuid4(), email="admin@example.com", hashed_password="already-hashed", role=UserRole.ADMIN
    )
    users = FakeUserRepository({"admin@example.com": existing})
    settings = _settings(
        default_admin_email="admin@example.com", default_admin_password="hunter2hunter2"
    )

    with patch.object(bootstrap, "get_settings", return_value=settings):
        await bootstrap.ensure_default_admin(users)

    # No second account created, and the existing one's password untouched.
    assert users.created == []
    assert users.users["admin@example.com"].hashed_password == "already-hashed"
