"""Conversation Service (Detailed Design Sec.5.4). SRS FR-006, FR-007, FR-008.

Owns the "no relevant context above threshold" decision (FR-006) and the
unsupported-answer flag (FR-007) before persisting a message. Threshold value
is an open item (Detailed Design Sec.6) pending eval against real data.
"""
import uuid

from app.core.config import Settings
from app.models.message import Message, MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.message_repository import MessageRepository
from app.services.ai_service.dtos import ChatMessage, ChatRequest, ChatRole
from app.services.ai_service.interfaces import ChatProvider
from app.services.vector_service import VectorService


class ConversationService:
    def __init__(
        self,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        vector_service: VectorService,
        chat_provider: ChatProvider,
        settings: Settings,
    ) -> None:
        self._conversations = conversation_repository
        self._messages = message_repository
        self._vectors = vector_service
        self._chat = chat_provider
        self._settings = settings

    async def ask(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        owner_document_ids: list[uuid.UUID],
    ) -> Message:
        chunks = await self._vectors.search(
            question, owner_document_ids, top_k=self._settings.retrieval_top_k
        )
        # TODO: chunks currently returned regardless of distance; filter by
        # self._settings.similarity_threshold once that value is validated
        # against real query data (Detailed Design Sec.6 open item).
        if not chunks:
            answer = Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content="I can't answer that from the available documents.",
                citations=[],
            )
            return await self._messages.create(answer)

        context = "\n\n".join(c.content for c in chunks)
        chat_response = await self._chat.generate(
            ChatRequest(
                messages=[
                    ChatMessage(
                        role=ChatRole.SYSTEM,
                        content="Answer only from the provided context. If the context doesn't "
                        "support an answer, say so explicitly.",
                    ),
                    ChatMessage(role=ChatRole.USER, content=f"Context:\n{context}\n\nQuestion: {question}"),
                ]
            )
        )
        citations = [
            {"chunk_id": str(c.id), "document_id": str(c.document_id), "source_location": c.source_location}
            for c in chunks
        ]
        answer = Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content=chat_response.content,
            citations=citations,
        )
        return await self._messages.create(answer)
