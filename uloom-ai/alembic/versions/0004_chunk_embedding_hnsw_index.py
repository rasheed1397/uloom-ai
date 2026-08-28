"""HNSW index on chunks.embedding_vector

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-28

Detailed Design Sec.5.3 "open question": index type/tuning for pgvector.
HNSW over IVFFlat - no training step needed on an empty/small table (IVFFlat
needs representative data present *before* the index is built to pick good
cluster centroids, which doesn't fit this app's index-at-migration-time
lifecycle), and better recall/speed at query time for the volumes this
platform targets.

Indexed on a halfvec(3072) cast, not the vector(3072) column directly:
pgvector caps both HNSW and IVFFlat at 2000 dimensions for the `vector`
type, but EMBEDDING_DIM (app/models/chunk.py) is 3072 (gemini-embedding-001's
output size) - over that cap. halfvec lifts the HNSW ceiling to 4000
dimensions at half-precision storage for the *index* only; the column
itself stays full-precision vector(3072), so nothing about stored/returned
embeddings changes, only the ANN index's internal representation (a normal,
expected precision/speed tradeoff for an *approximate* nearest-neighbor
index). ChunkRepository.similarity_search casts the query the same way, so
the planner can actually match this expression index.
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMBEDDING_DIM = 3072


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX ix_chunks_embedding_vector_hnsw ON chunks "
        f"USING hnsw ((embedding_vector::halfvec({_EMBEDDING_DIM})) halfvec_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_chunks_embedding_vector_hnsw")
