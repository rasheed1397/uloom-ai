"""App-startup bootstrap steps. Currently just the default admin account
(FR-009): ADMIN_BOOTSTRAP_EMAILS only promotes an email *when that person
registers*, so a fresh deployment where nobody has registered yet has no
way to reach /admin/* at all. This creates an actual admin account before
the app starts serving requests, if configured to - see Settings.
"""
import logging

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


async def ensure_default_admin(users: UserRepository) -> None:
    settings = get_settings()
    if not settings.default_admin_email or not settings.default_admin_password:
        return

    existing = await users.get_by_email(settings.default_admin_email)
    if existing is not None:
        # Already bootstrapped on a previous startup - idempotent by
        # design, since this runs every time the app boots, not once.
        return

    await users.create(
        User(
            email=settings.default_admin_email,
            hashed_password=hash_password(settings.default_admin_password),
            role=UserRole.ADMIN,
        )
    )
    logger.info("Created default admin account %s", settings.default_admin_email)
