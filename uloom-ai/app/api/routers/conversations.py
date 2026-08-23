"""Resource: /conversations, /conversations/{id}/messages (Detailed Design
Sec.4, SRS FR-006, FR-007, FR-008)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_conversation_service, get_document_service
from app.schemas.conversations import ConversationOut, CreateConversationRequest
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class AskRequest(BaseModel):
    question: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[dict]

    model_config = {"from_attributes": True}


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: CreateConversationRequest,
    user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> ConversationOut:
    conversation = await conversation_service.create(user_id=user.id, title=body.title)
    return ConversationOut.model_validate(conversation)


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: CurrentUser, conversation_service: Annotated[ConversationService, Depends(get_conversation_service)]
) -> list[ConversationOut]:
    conversations = await conversation_service.list_for_user(user.id)
    return [ConversationOut.model_validate(c) for c in conversations]


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def ask(
    conversation_id: uuid.UUID,
    body: AskRequest,
    user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
    document_service: Annotated[DocumentService, Depends(get_document_service)],
) -> MessageOut:
    conversation = await conversation_service.get_by_id(conversation_id)
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Scoped to documents the user owns; sharing (SRS Sec.10) isn't
    # implemented yet, so "owned" is the whole authorized set for now.
    owned_documents = await document_service.list_for_owner(user.id)
    message = await conversation_service.ask(
        conversation_id=conversation_id,
        user_id=user.id,
        question=body.question,
        owner_document_ids=[d.id for d in owned_documents],
    )
    return MessageOut.model_validate(message)
