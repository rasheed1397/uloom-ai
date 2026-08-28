"""system_settings.retention_days

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-28

SRS Section 10: default retention period for uploaded documents and
conversation history, admin-configurable via PATCH /admin/settings (same
pattern as retrieval_top_k/chunk_token_size/similarity_threshold).
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_RETENTION_DAYS = 90


def upgrade() -> None:
    op.add_column(
        "system_settings",
        sa.Column("retention_days", sa.Integer, nullable=False, server_default=str(DEFAULT_RETENTION_DAYS)),
    )
    op.alter_column("system_settings", "retention_days", server_default=None)


def downgrade() -> None:
    op.drop_column("system_settings", "retention_days")
