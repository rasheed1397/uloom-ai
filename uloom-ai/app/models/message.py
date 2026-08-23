"""Message entity (Detailed Design Sec.2 ERD; SRS FR-006, FR-007, FR-008)."""
import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, created_at_col, uuid_pk

if TYPE_CHECKING:
    from app.models.conversation import Conversation


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, values_callable=lambda cls: [e.value for e in cls]), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # List of {chunk_id, document_id, source_location} — FR-007 citation-aware answers.
    # Empty list means "unsupported" (no grounding found above threshold), per FR-006/FR-007.
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = created_at_col()

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")  # noqa: F821
