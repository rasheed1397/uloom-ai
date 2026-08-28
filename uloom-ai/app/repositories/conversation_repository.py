import uuid
from datetime import datetime

from sqlalchemy import select

from app.models.conversation import Conversation
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository):
    async def create(self, conversation: Conversation) -> Conversation:
        self._session.add(conversation)
        await self._session.flush()
        return conversation

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return await self._session.get(Conversation, conversation_id)

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())  # FR-008: reverse-chronological
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_older_than(self, cutoff: datetime) -> list[Conversation]:
        # Sec.10 retention sweep, platform-wide across every user.
        result = await self._session.execute(
            select(Conversation).where(Conversation.created_at < cutoff)
        )
        return list(result.scalars().all())

    async def delete(self, conversation: Conversation) -> None:
        # Message rows cascade via Conversation.messages'
        # cascade="all, delete-orphan" (app/models/conversation.py).
        await self._session.delete(conversation)
        await self._session.flush()
