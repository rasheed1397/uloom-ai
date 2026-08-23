import uuid

import pytest

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.message import Message, MessageRole
from app.services.ai_service.dtos import ChatRequest, ChatResponse
from app.services.conversation_service import ConversationService


class FakeVectorService:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks

    async def search(self, query: str, owner_document_ids: list[uuid.UUID], top_k: int) -> list[Chunk]:
        return self.chunks


class FakeChatProvider:
    def __init__(self, content: str) -> None:
        self.content = content
        self.last_request: ChatRequest | None = None

    async def generate(self, request: ChatRequest) -> ChatResponse:
        self.last_request = request
        return ChatResponse(content=self.content)

    @property
    def capabilities(self):
        raise NotImplementedError


class FakeMessageRepository:
    def __init__(self) -> None:
        self.created: list[Message] = []

    async def create(self, message: Message) -> Message:
        self.created.append(message)
        return message


@pytest.fixture
def settings() -> Settings:
    return Settings(retrieval_top_k=5)


async def test_ask_returns_unsupported_message_when_no_chunks_found(settings: Settings):
    messages = FakeMessageRepository()
    chat = FakeChatProvider(content="should not be called")
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=FakeVectorService(chunks=[]),
        chat_provider=chat,
        settings=settings,
    )

    answer = await service.ask(
        conversation_id=uuid.uuid4(), user_id=uuid.uuid4(), question="anything?", owner_document_ids=[]
    )

    assert answer.role == MessageRole.ASSISTANT
    assert answer.citations == []
    assert "can't answer" in answer.content
    assert messages.created == [answer]
    assert chat.last_request is None


async def test_ask_answers_from_retrieved_chunks_with_citations(settings: Settings):
    document_id = uuid.uuid4()
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document_id,
        content="Paris is the capital of France.",
        token_count=8,
        source_location={"page": 1},
    )
    messages = FakeMessageRepository()
    chat = FakeChatProvider(content="Paris.")
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=FakeVectorService(chunks=[chunk]),
        chat_provider=chat,
        settings=settings,
    )

    answer = await service.ask(
        conversation_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        question="What is the capital of France?",
        owner_document_ids=[document_id],
    )

    assert answer.content == "Paris."
    assert answer.citations == [
        {"chunk_id": str(chunk.id), "document_id": str(document_id), "source_location": {"page": 1}}
    ]
    assert chat.last_request is not None
    assert "Paris is the capital of France." in chat.last_request.messages[-1].content
