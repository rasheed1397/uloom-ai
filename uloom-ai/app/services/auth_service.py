"""Auth Service (Detailed Design Sec.5.1). Framework-agnostic; the API layer
handles HTTP concerns, this handles the actual registration/login logic."""
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


class EmailAlreadyRegisteredError(Exception): ...


class InvalidCredentialsError(Exception): ...


class AuthService:
    def __init__(self, user_repository: UserRepository) -> None:
        self._users = user_repository

    async def register(self, email: str, password: str) -> tuple[User, str]:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(email)
        user = User(email=email, hashed_password=hash_password(password), role=UserRole.STANDARD)
        user = await self._users.create(user)
        token = create_access_token(subject=str(user.id), role=user.role.value)
        return user, token

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self._users.get_by_email(email)
        # Same error regardless of which part was wrong (FR-001 acceptance
        # criteria: don't reveal whether the email or password was incorrect).
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError
        token = create_access_token(subject=str(user.id), role=user.role.value)
        return user, token
