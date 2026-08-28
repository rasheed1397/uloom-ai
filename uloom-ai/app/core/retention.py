"""Data retention sweep (SRS Section 10: "Define and document a default
retention period for uploaded documents and conversation history,
configurable by Administrators.").

Runs as a periodic background task from app.main's lifespan rather than an
external cron job, so retention works out of the box in a single-container
deployment without adding a scheduler dependency (APScheduler/Celery) the
codebase doesn't otherwise need. retention_days is re-read from
system_settings on every sweep rather than cached at startup, so an admin's
PATCH /admin/settings change takes effect on the next sweep without a
restart (same FR-009 runtime-without-redeploy pattern as retrieval_top_k /
chunk_token_size / similarity_threshold).

Default: 90 days. Applies platform-wide, across every user's documents and
conversations - Section 10 describes a default retention *period*, not a
per-user setting.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.db import SessionLocal
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.system_settings_repository import SystemSettingsRepository
from app.services.document_service import document_storage_key
from app.services.storage.factory import get_storage_backend

logger = logging.getLogger(__name__)

_SWEEP_INTERVAL_SECONDS = 24 * 60 * 60


async def run_retention_sweep_periodically(interval_seconds: float = _SWEEP_INTERVAL_SECONDS) -> None:
    while True:
        try:
            await run_retention_sweep()
        except Exception:
            # Sec.9's "failures shall not terminate the application" applies
            # here too: a bad sweep must never crash the app or block the
            # next scheduled one.
            logger.exception("Retention sweep failed")
        await asyncio.sleep(interval_seconds)


async def run_retention_sweep() -> tuple[int, int]:
    """Deletes documents and conversations older than the admin-configured
    retention_days. Returns (documents_deleted, conversations_deleted)."""
    storage = get_storage_backend()
    async with SessionLocal() as session, session.begin():
        settings = await SystemSettingsRepository(session).get()
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)

        documents = DocumentRepository(session)
        expired_documents = await documents.list_older_than(cutoff)
        for document in expired_documents:
            await storage.delete(document_storage_key(document.id))
            await documents.delete(document)

        conversations = ConversationRepository(session)
        expired_conversations = await conversations.list_older_than(cutoff)
        for conversation in expired_conversations:
            await conversations.delete(conversation)

    if expired_documents or expired_conversations:
        logger.info(
            "Retention sweep purged %d document(s) and %d conversation(s) older than %d day(s)",
            len(expired_documents),
            len(expired_conversations),
            settings.retention_days,
        )
    return len(expired_documents), len(expired_conversations)
