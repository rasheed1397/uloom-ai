"""system_settings singleton table

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-23
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Matches app.core.config.Settings' defaults - the seed row's starting
# values, from here on mutable via PATCH /admin/settings (FR-009) without
# needing a redeploy.
DEFAULT_RETRIEVAL_TOP_K = 5
DEFAULT_CHUNK_TOKEN_SIZE = 512
DEFAULT_SIMILARITY_THRESHOLD = 0.7

def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("retrieval_top_k", sa.Integer, nullable=False),
        sa.Column("chunk_token_size", sa.Integer, nullable=False),
        sa.Column("similarity_threshold", sa.Float, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    # Singleton row: id is always 1. Seeded here so the app can assume it
    # exists rather than handling a "not configured yet" case everywhere.
    # created_at/updated_at are NOT NULL, so they're set in the same insert
    # (via now()) rather than a separate UPDATE afterward.
    op.execute(
        f"""
        INSERT INTO system_settings
            (id, retrieval_top_k, chunk_token_size, similarity_threshold, created_at, updated_at)
        VALUES
            (1, {DEFAULT_RETRIEVAL_TOP_K}, {DEFAULT_CHUNK_TOKEN_SIZE}, {DEFAULT_SIMILARITY_THRESHOLD},
             now(), now())
        """
    )


def downgrade() -> None:
    op.drop_table("system_settings")
