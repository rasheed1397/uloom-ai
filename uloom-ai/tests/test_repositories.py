import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import EMBEDDING_DIM, Chunk
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import Message, MessageRole
from app.models.user import User, UserRole
from app.repositories.chunk_repository import ChunkRepository
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.message_repository import MessageRepository
from app.repositories.user_repository import UserRepository


def _unit_vector(hot_index: int, sign: float = 1.0) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    vector[hot_index] = sign
    return vector


async def _make_user(session: AsyncSession, email: str = "repo@example.com") -> User:
    return await UserRepository(session).create(
        User(email=email, hashed_password="hashed", role=UserRole.STANDARD)
    )


async def _make_document(session: AsyncSession, owner_id: uuid.UUID) -> Document:
    return await DocumentRepository(session).create(
        Document(owner_id=owner_id, filename="doc.pdf", mime_type="application/pdf")
    )


async def test_user_repository_create_and_lookup(db_session: AsyncSession):
    repo = UserRepository(db_session)
    created = await repo.create(User(email="lookup@example.com", hashed_password="hashed"))

    assert await repo.get_by_email("lookup@example.com") == created
    assert await repo.get_by_id(created.id) == created
    assert await repo.get_by_email("missing@example.com") is None


async def test_document_repository_create_get_and_list_for_owner(db_session: AsyncSession):
    user = await _make_user(db_session)
    other_user = await _make_user(db_session, email="other@example.com")
    repo = DocumentRepository(db_session)
    doc = await repo.create(Document(owner_id=user.id, filename="a.pdf", mime_type="application/pdf"))
    await repo.create(Document(owner_id=other_user.id, filename="b.pdf", mime_type="application/pdf"))

    assert await repo.get_by_id(doc.id) == doc
    owned = await repo.list_for_owner(user.id)
    assert owned == [doc]


async def test_conversation_repository_create_get_and_list_ordering(db_session: AsyncSession):
    user = await _make_user(db_session)
    repo = ConversationRepository(db_session)
    first = await repo.create(Conversation(user_id=user.id, title="first"))
    second = await repo.create(Conversation(user_id=user.id, title="second"))
    second.title = "second-updated"
    await db_session.flush()

    assert await repo.get_by_id(first.id) == first
    listed = await repo.list_for_user(user.id)
    assert listed[0] == second
    assert first in listed


async def test_message_repository_create_and_list_for_conversation(db_session: AsyncSession):
    user = await _make_user(db_session)
    conversation = await ConversationRepository(db_session).create(Conversation(user_id=user.id))
    repo = MessageRepository(db_session)
    first = await repo.create(
        Message(conversation_id=conversation.id, role=MessageRole.USER, content="hi", citations=[])
    )
    second = await repo.create(
        Message(conversation_id=conversation.id, role=MessageRole.ASSISTANT, content="hello", citations=[])
    )

    listed = await repo.list_for_conversation(conversation.id)
    assert listed == [first, second]


async def test_chunk_repository_bulk_create_and_similarity_search(db_session: AsyncSession):
    user = await _make_user(db_session)
    document = await _make_document(db_session, user.id)
    other_document = await _make_document(db_session, user.id)
    repo = ChunkRepository(db_session)

    closest = Chunk(
        document_id=document.id, content="closest", token_count=1, embedding_vector=_unit_vector(0)
    )
    near = Chunk(
        document_id=document.id, content="near", token_count=1, embedding_vector=_unit_vector(1)
    )
    far = Chunk(
        document_id=document.id, content="far", token_count=1, embedding_vector=_unit_vector(0, sign=-1.0)
    )
    other_docs_chunk = Chunk(
        document_id=other_document.id,
        content="different document",
        token_count=1,
        embedding_vector=_unit_vector(0),
    )
    await repo.bulk_create([closest, near, far, other_docs_chunk])

    results = await repo.similarity_search(
        query_vector=_unit_vector(0), owner_document_ids=[document.id], top_k=2
    )

    assert results == [closest, near]
