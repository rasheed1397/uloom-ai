import uuid

from app.api.routers.conversations import AskRequest, ask
from app.models.message import Message, MessageRole
from app.models.user import User, UserRole


class FakeConversationService:
    def __init__(self, answer: Message) -> None:
        self.answer = answer
        self.last_call: dict | None = None

    async def ask(self, conversation_id, user_id, question, owner_document_ids):
        self.last_call = {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "question": question,
            "owner_document_ids": owner_document_ids,
        }
        return self.answer


async def test_ask_route_delegates_to_conversation_service_and_serializes_response():
    conversation_id = uuid.uuid4()
    user = User(id=uuid.uuid4(), email="asker@example.com", hashed_password="x", role=UserRole.STANDARD)
    answer = Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="42",
        citations=[],
    )
    service = FakeConversationService(answer)

    result = await ask(
        conversation_id=conversation_id,
        body=AskRequest(question="What is the answer?"),
        user=user,
        conversation_service=service,
    )

    assert result.id == answer.id
    assert result.content == "42"
    assert service.last_call == {
        "conversation_id": conversation_id,
        "user_id": user.id,
        "question": "What is the answer?",
        "owner_document_ids": [],
    }
