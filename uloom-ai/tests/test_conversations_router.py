import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.routers.conversations import (
    AskRequest,
    ask,
    create_conversation,
    list_conversations,
    list_messages,
)
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message, MessageRole
from app.models.user import User, UserRole
from app.schemas.conversations import CreateConversationRequest


def _make_conversation(user_id: uuid.UUID, title: str = "New conversation") -> Conversation:
    # created_at/updated_at are DB-applied defaults (SQLAlchemy flush time),
    # not Python constructor defaults, so they need setting explicitly here
    # or ConversationOut's serialization fails validation on None.
    now = datetime.now(timezone.utc)
    return Conversation(id=uuid.uuid4(), user_id=user_id, title=title, created_at=now, updated_at=now)


class FakeConversationService:
    def __init__(
        self,
        conversation: Conversation | None = None,
        answer: Message | None = None,
        messages: list[Message] | None = None,
    ) -> None:
        self.conversation = conversation
        self.answer = answer
        self.messages = messages or []
        self.created: list[tuple[uuid.UUID, str | None]] = []
        self.last_ask_call: dict | None = None

    async def create(self, user_id: uuid.UUID, title: str | None) -> Conversation:
        self.created.append((user_id, title))
        return _make_conversation(user_id, title=title or "New conversation")

    async def list_for_user(self, user_id: uuid.UUID) -> list[Conversation]:
        return [self.conversation] if self.conversation and self.conversation.user_id == user_id else []

    async def get_by_id(self, conversation_id: uuid.UUID) -> Conversation | None:
        if self.conversation and self.conversation.id == conversation_id:
            return self.conversation
        return None

    async def list_messages(self, conversation_id: uuid.UUID) -> list[Message]:
        return self.messages

    async def ask(self, conversation_id, user_id, question, owner_document_ids):
        self.last_ask_call = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "question": question,
            "owner_document_ids": owner_document_ids,
        }
        return self.answer


class FakeDocumentService:
    def __init__(self, documents: list[Document]) -> None:
        self.documents = documents

    async def list_for_owner(self, owner_id: uuid.UUID) -> list[Document]:
        return self.documents


def _user() -> User:
    return User(id=uuid.uuid4(), email="asker@example.com", hashed_password="x", role=UserRole.STANDARD)


async def test_create_conversation_delegates_to_service():
    user = _user()
    service = FakeConversationService()

    result = await create_conversation(
        body=CreateConversationRequest(title="Docs Q&A"), user=user, conversation_service=service
    )

    assert result.title == "Docs Q&A"
    assert service.created == [(user.id, "Docs Q&A")]


async def test_list_conversations_scoped_to_current_user():
    user = _user()
    conversation = _make_conversation(user.id, title="Mine")
    service = FakeConversationService(conversation=conversation)

    result = await list_conversations(user=user, conversation_service=service)

    assert [c.id for c in result] == [conversation.id]


async def test_list_messages_returns_history_for_owned_conversation():
    user = _user()
    conversation = _make_conversation(user.id, title="Mine")
    message = Message(
        id=uuid.uuid4(), conversation_id=conversation.id, role=MessageRole.USER, content="hi", citations=[]
    )
    service = FakeConversationService(conversation=conversation, messages=[message])

    result = await list_messages(conversation_id=conversation.id, user=user, conversation_service=service)

    assert [m.id for m in result] == [message.id]


async def test_list_messages_404s_for_conversation_the_user_does_not_own():
    user = _user()
    other_conversation = _make_conversation(uuid.uuid4(), title="Not mine")
    service = FakeConversationService(conversation=other_conversation)

    with pytest.raises(HTTPException) as exc_info:
        await list_messages(conversation_id=other_conversation.id, user=user, conversation_service=service)
    assert exc_info.value.status_code == 404


async def test_list_messages_404s_for_nonexistent_conversation():
    user = _user()
    service = FakeConversationService(conversation=None)

    with pytest.raises(HTTPException) as exc_info:
        await list_messages(conversation_id=uuid.uuid4(), user=user, conversation_service=service)
    assert exc_info.value.status_code == 404


async def test_ask_route_delegates_to_conversation_service_and_serializes_response():
    user = _user()
    conversation = _make_conversation(user.id, title="Mine")
    owned_document = Document(id=uuid.uuid4(), owner_id=user.id, filename="a.txt", mime_type="text/plain")
    answer = Message(
        id=uuid.uuid4(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content="42",
        citations=[],
    )
    conversation_service = FakeConversationService(conversation=conversation, answer=answer)
    document_service = FakeDocumentService([owned_document])

    result = await ask(
        conversation_id=conversation.id,
        body=AskRequest(question="What is the answer?"),
        user=user,
        conversation_service=conversation_service,
        document_service=document_service,
    )

    assert result.id == answer.id
    assert result.content == "42"
    assert conversation_service.last_ask_call == {
        "conversation_id": conversation.id,
        "user_id": user.id,
        "question": "What is the answer?",
        "owner_document_ids": [owned_document.id],
    }


async def test_ask_404s_for_conversation_the_user_does_not_own():
    user = _user()
    other_conversation = _make_conversation(uuid.uuid4(), title="Not mine")
    conversation_service = FakeConversationService(conversation=other_conversation)
    document_service = FakeDocumentService([])

    with pytest.raises(HTTPException) as exc_info:
        await ask(
            conversation_id=other_conversation.id,
            body=AskRequest(question="hi"),
            user=user,
            conversation_service=conversation_service,
            document_service=document_service,
        )
    assert exc_info.value.status_code == 404
    assert conversation_service.last_ask_call is None
