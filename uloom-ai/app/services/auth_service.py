"""Auth Service (Detailed Design Sec.5.1). Framework-agnostic; the API layer
handles HTTP concerns, this handles the actual registration/login logic."""
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository


class EmailAlreadyRegisteredError(Exception): ...


class InvalidCredentialsError(Exception): ...


class AuthService:
    def __init__(self, user_repository: UserRepository, admin_bootstrap_emails: str = "") -> None:
        self._users = user_repository
        # FR-009 open item: how the first Administrator is created. Resolved
        # as a config-driven allowlist checked once at registration, so
        # there's no privilege-escalation API surface and no chicken-and-egg
        # "need an admin to create an admin" problem. Ongoing role changes
        # go through PATCH /admin/users/{id} (AdminService.update_user).
        self._admin_bootstrap_emails = {
            e.strip().lower() for e in admin_bootstrap_emails.split(",") if e.strip()
        }

    async def register(self, email: str, password: str) -> tuple[User, str]:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError(email)
        role = UserRole.ADMIN if email.lower() in self._admin_bootstrap_emails else UserRole.STANDARD
        user = User(email=email, hashed_password=hash_password(password), role=role)
        user = await self._users.create(user)
        token = create_access_token(subject=str(user.id), role=user.role.value)
        return user, token

    async def login(self, email: str, password: str) -> tuple[User, str]:
        user = await self._users.get_by_email(email)
        # Same error regardless of which part was wrong (FR-001 acceptance
        # criteria: don't reveal whether the email or password was incorrect).
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError
        if not user.is_active:
            raise InvalidCredentialsError
        token = create_access_token(subject=str(user.id), role=user.role.value)
        return user, token

    async def update_profile(self, user: User, email: str | None, password: str | None) -> User:
        """Self-service profile update (FR-002). Role is deliberately not
        settable here - see UpdateProfileRequest."""
        if email is not None and email != user.email:
            existing = await self._users.get_by_email(email)
            if existing is not None and existing.id != user.id:
                raise EmailAlreadyRegisteredError(email)
            user.email = email
        if password is not None:
            user.hashed_password = hash_password(password)
        return user
