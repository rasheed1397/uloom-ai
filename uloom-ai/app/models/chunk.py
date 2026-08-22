"""Chunk entity — pgvector-backed (Detailed Design Sec.2 ERD; SRS FR-004, FR-005)."""
import uuid
from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, uuid_pk

if TYPE_CHECKING:
    from app.models.document import Document

# Dimension matches the default embedding provider's output size
# (gemini-embedding-001; Detailed Design Sec.5.5). Revisit if the
# embedding provider or its output dimension changes.
EMBEDDING_DIM = 3072


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_vector: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    source_location: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    document: Mapped["Document"] = relationship(back_populates="chunks")  # noqa: F821
