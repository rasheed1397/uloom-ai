"""document status_detail and user is_active

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-23
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # FR-004/Sec.9: a failed indexing run needs a visible reason, not just a status.
    op.add_column("documents", sa.Column("status_detail", sa.Text, nullable=True))
    # FR-009: admins can disable accounts.
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true())
    )


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("documents", "status_detail")
