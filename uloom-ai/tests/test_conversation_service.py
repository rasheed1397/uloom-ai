import uuid

import pytest

from app.core.config import Settings
from app.models.chunk import Chunk
from app.models.conversation import Conversation
from app.models.message import Message, MessageRole
from app.services.ai_service.dtos import ChatRequest, ChatResponse
from app.services.ai_service.interfaces import ProviderError
from app.services.conversation_service import ConversationService


class FakeVectorService:
    def __init__(self, chunks: list[Chunk] | None = None, error: Exception | None = None) -> None:
        self.chunks = chunks or []
        self.error = error
        self.last_similarity_threshold: float | None = None

    async def search(
        self,
        query: str,
        owner_document_ids: list[uuid.UUID],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[Chunk]:
        self.last_similarity_threshold = similarity_threshold
        if self.error:
            raise self.error
        return self.chunks


class FakeConversationRepository:
    def __init__(self) -> None:
        self.created: list[Conversation] = []

    async def create(self, conversation: Conversation) -> Conversation:
        conversation.id = uuid.uuid4()
        # Mirrors the DB: Conversation.title's default is applied by
        # SQLAlchemy at INSERT/flush time, not by the Python constructor.
        if conversation.title is None:
            conversation.title = "New conversation"
        self.created.append(conversation)
        return conversation

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        return [c for c in self.created if c.user_id == user_id]

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        return next((c for c in self.created if c.id == conversation_id), None)


class FakeChatProvider:
    def __init__(self, content: str = "", error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.last_request: ChatRequest | None = None

    async def generate(self, request: ChatRequest) -> ChatResponse:
        self.last_request = request
        if self.error:
            raise self.error
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

    async def list_for_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        return [m for m in self.created if m.conversation_id == conversation_id]


@pytest.fixture
def settings() -> Settings:
    return Settings(retrieval_top_k=5)


async def test_ask_returns_unsupported_message_when_no_chunks_found(settings: Settings):
    messages = FakeMessageRepository()
    chat = FakeChatProvider(content="should not be called")
    vector_service = FakeVectorService(chunks=[])
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=vector_service,
        chat_provider=chat,
        settings=settings,
    )

    answer = await service.ask(
        conversation_id=uuid.uuid4(), user_id=uuid.uuid4(), question="anything?", owner_document_ids=[]
    )

    assert answer.role == MessageRole.ASSISTANT
    assert answer.citations == []
    assert "can't answer" in answer.content
    # ask() persists the user's question first, unconditionally, then the
    # answer - so both should be in history even on this degraded path.
    assert len(messages.created) == 2
    # FR-006: the configured threshold is passed through to VectorService,
    # which is what excludes below-threshold chunks (an empty list here
    # already means "nothing similar enough", not just "no documents").
    assert vector_service.last_similarity_threshold == settings.similarity_threshold
    assert messages.created[0].role == MessageRole.USER
    assert messages.created[0].content == "anything?"
    assert messages.created[1] is answer
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


async def test_ask_degrades_gracefully_when_search_fails(settings: Settings):
    messages = FakeMessageRepository()
    chat = FakeChatProvider(content="should not be called")
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=FakeVectorService(error=ProviderError("provider down")),
        chat_provider=chat,
        settings=settings,
    )

    answer = await service.ask(
        conversation_id=uuid.uuid4(), user_id=uuid.uuid4(), question="anything?", owner_document_ids=[]
    )

    assert answer.content == "Search is temporarily unavailable."
    assert chat.last_request is None
    # Question still recorded even though search failed.
    assert messages.created[0].role == MessageRole.USER


async def test_ask_degrades_gracefully_when_chat_generation_fails(settings: Settings):
    chunk = Chunk(
        id=uuid.uuid4(), document_id=uuid.uuid4(), content="some context", token_count=2, source_location={}
    )
    messages = FakeMessageRepository()
    chat = FakeChatProvider(error=ProviderError("provider down"))
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=FakeVectorService(chunks=[chunk]),
        chat_provider=chat,
        settings=settings,
    )

    answer = await service.ask(
        conversation_id=uuid.uuid4(), user_id=uuid.uuid4(), question="anything?", owner_document_ids=[]
    )

    assert answer.content == "Answer temporarily unavailable."
    assert answer.citations == []


async def test_create_persists_conversation_for_user(settings: Settings):
    conversations = FakeConversationRepository()
    service = ConversationService(
        conversation_repository=conversations,
        message_repository=FakeMessageRepository(),
        vector_service=FakeVectorService(),
        chat_provider=FakeChatProvider(),
        settings=settings,
    )
    user_id = uuid.uuid4()

    conversation = await service.create(user_id=user_id, title="My chat")

    assert conversation.user_id == user_id
    assert conversation.title == "My chat"
    assert conversations.created == [conversation]


async def test_create_uses_default_title_when_none_given(settings: Settings):
    conversations = FakeConversationRepository()
    service = ConversationService(
        conversation_repository=conversations,
        message_repository=FakeMessageRepository(),
        vector_service=FakeVectorService(),
        chat_provider=FakeChatProvider(),
        settings=settings,
    )

    conversation = await service.create(user_id=uuid.uuid4(), title=None)

    assert conversation.title == "New conversation"


async def test_list_for_user_and_get_by_id_delegate_to_repository(settings: Settings):
    conversations = FakeConversationRepository()
    service = ConversationService(
        conversation_repository=conversations,
        message_repository=FakeMessageRepository(),
        vector_service=FakeVectorService(),
        chat_provider=FakeChatProvider(),
        settings=settings,
    )
    user_id = uuid.uuid4()
    mine = await service.create(user_id=user_id, title=None)
    await service.create(user_id=uuid.uuid4(), title=None)

    assert await service.list_for_user(user_id) == [mine]
    assert await service.get_by_id(mine.id) is mine
    assert await service.get_by_id(uuid.uuid4()) is None


async def test_list_messages_delegates_to_repository(settings: Settings):
    messages = FakeMessageRepository()
    conversation_id = uuid.uuid4()
    existing = Message(conversation_id=conversation_id, role=MessageRole.USER, content="hi", citations=[])
    other = Message(conversation_id=uuid.uuid4(), role=MessageRole.USER, content="other", citations=[])
    messages.created.extend([existing, other])
    service = ConversationService(
        conversation_repository=None,
        message_repository=messages,
        vector_service=FakeVectorService(),
        chat_provider=FakeChatProvider(),
        settings=settings,
    )

    result = await service.list_messages(conversation_id)

    assert result == [existing]
