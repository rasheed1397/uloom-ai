"""System-wide, admin-adjustable retrieval/chunking tuning (FR-009: "system
settings... configurable without a deployment"). A deliberate singleton
table - always exactly one row, id fixed at 1 by the seeding migration - so
reading/updating it doesn't need a lookup key. Distinct from app.core.config
.Settings, which stays env-file/deployment-time config (secrets, provider
selection, storage paths); this table is the runtime-mutable subset SRS
Section 8's admin controls, and only that subset.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, created_at_col


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    retrieval_top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_token_size: Mapped[int] = mapped_column(Integer, nullable=False)
    similarity_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    # SRS Section 10: "define and document a default retention period for
    # uploaded documents and conversation history, configurable by
    # Administrators." Read fresh on every retention sweep (app.core.
    # retention), not cached, so a PATCH here takes effect on the next
    # sweep without a restart - same pattern as the three fields above.
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
