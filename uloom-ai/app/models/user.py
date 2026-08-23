"""User entity (Detailed Design Sec.2 ERD; SRS FR-001, FR-002)."""
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.conversation import Conversation
    from app.models.document import Document


class UserRole(str, enum.Enum):
    STANDARD = "standard"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda cls: [e.value for e in cls]),
        default=UserRole.STANDARD,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    documents: Mapped[list["Document"]] = relationship(back_populates="owner")  # noqa: F821
    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")  # noqa: F821
