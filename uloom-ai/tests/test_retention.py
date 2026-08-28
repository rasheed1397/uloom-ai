import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import retention
from app.core.retention import run_retention_sweep, run_retention_sweep_periodically
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.system_settings import SystemSettings
from app.models.user import User
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.user_repository import UserRepository


async def _make_user(session: AsyncSession) -> User:
    return await UserRepository(session).create(
        User(email=f"{uuid.uuid4()}@example.com", hashed_password="hashed")
    )


async def _set_retention_days(session: AsyncSession, days: int) -> None:
    settings = await session.get(SystemSettings, 1)
    settings.retention_days = days
    await session.flush()


@pytest.mark.asyncio
async def test_sweep_purges_documents_and_conversations_older_than_retention(db_session: AsyncSession):
    user = await _make_user(db_session)
    old_cutoff = datetime.now(timezone.utc) - timedelta(days=200)

    old_document = await DocumentRepository(db_session).create(
        Document(owner_id=user.id, filename="old.pdf", mime_type="application/pdf")
    )
    old_document.created_at = old_cutoff
    recent_document = await DocumentRepository(db_session).create(
        Document(owner_id=user.id, filename="recent.pdf", mime_type="application/pdf")
    )

    old_conversation = await ConversationRepository(db_session).create(Conversation(user_id=user.id))
    old_conversation.created_at = old_cutoff
    recent_conversation = await ConversationRepository(db_session).create(Conversation(user_id=user.id))

    await _set_retention_days(db_session, days=90)
    await db_session.commit()

    # Captured before the sweep: expire_all() below marks every attribute on
    # these objects (including .id) as expired, and reading an expired
    # attribute triggers an implicit *synchronous* refresh that AsyncSession
    # can't service outside an active greenlet context (MissingGreenlet).
    old_document_id, recent_document_id = old_document.id, recent_document.id
    old_conversation_id, recent_conversation_id = old_conversation.id, recent_conversation.id

    documents_purged, conversations_purged = await run_retention_sweep()

    # run_retention_sweep deletes via its own separate session/connection
    # (app.core.retention); db_session's identity map doesn't know that -
    # SessionLocal is expire_on_commit=False (app/core/db.py), so .get()
    # would otherwise happily return the stale in-memory object instead of
    # re-querying. expire_all() forces a fresh read.
    db_session.expire_all()

    assert documents_purged == 1
    assert conversations_purged == 1
    assert await db_session.get(Document, old_document_id) is None
    assert await db_session.get(Document, recent_document_id) is not None
    assert await db_session.get(Conversation, old_conversation_id) is None
    assert await db_session.get(Conversation, recent_conversation_id) is not None


@pytest.mark.asyncio
async def test_sweep_respects_admin_configured_retention_days(db_session: AsyncSession):
    user = await _make_user(db_session)
    thirty_days_old = datetime.now(timezone.utc) - timedelta(days=30)

    document = await DocumentRepository(db_session).create(
        Document(owner_id=user.id, filename="a.pdf", mime_type="application/pdf")
    )
    document.created_at = thirty_days_old

    # Default retention (90 days) would keep this; a stricter admin-set
    # value (7 days) must purge it - proves the sweep reads the live
    # setting rather than a hardcoded window.
    await _set_retention_days(db_session, days=7)
    await db_session.commit()

    document_id = document.id  # see the expire_all() comment in the test above
    documents_purged, _ = await run_retention_sweep()
    db_session.expire_all()

    assert documents_purged == 1
    assert await db_session.get(Document, document_id) is None


@pytest.mark.asyncio
async def test_sweep_purges_nothing_when_everything_is_within_retention(db_session: AsyncSession):
    user = await _make_user(db_session)
    await DocumentRepository(db_session).create(
        Document(owner_id=user.id, filename="fresh.pdf", mime_type="application/pdf")
    )
    await _set_retention_days(db_session, days=90)
    await db_session.commit()

    documents_purged, conversations_purged = await run_retention_sweep()

    assert (documents_purged, conversations_purged) == (0, 0)


@pytest.mark.asyncio
async def test_periodic_sweep_survives_a_failing_iteration(monkeypatch: pytest.MonkeyPatch):
    """Sec.9's "failures shall not terminate the application" applies to the
    sweep itself, not just AI-provider calls: a failing iteration must be
    caught and logged, not propagate out of the loop.

    Deliberately doesn't spin the loop up as a background task and let it
    free-run for a few event-loop turns - a fake `asyncio.sleep` that
    doesn't itself yield to the loop turns `while True` into a genuine
    infinite loop with no suspension point at all, since a failing sweep
    call also returns without awaiting anything. That starves the
    session-scoped test event loop outright rather than just running fast.
    Instead: let exactly one failing iteration happen, then have the mocked
    sleep raise CancelledError to end the loop deterministically - proves
    the RuntimeError was caught (the loop reached the sleep at all) without
    ever looping unboundedly.
    """
    calls = 0

    async def _failing_sweep() -> tuple[int, int]:
        nonlocal calls
        calls += 1
        raise RuntimeError("db unavailable")

    async def _sleep_then_cancel(_seconds: float) -> None:
        raise asyncio.CancelledError

    monkeypatch.setattr(retention, "run_retention_sweep", _failing_sweep)
    monkeypatch.setattr(retention.asyncio, "sleep", _sleep_then_cancel)

    with pytest.raises(asyncio.CancelledError):
        await run_retention_sweep_periodically()

    assert calls == 1
