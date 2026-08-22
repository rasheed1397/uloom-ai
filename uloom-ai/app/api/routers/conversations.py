"""Resource: /conversations, /conversations/{id}/messages (Detailed Design
Sec.4, SRS FR-006, FR-007, FR-008)."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import CurrentUser, get_conversation_service
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


class AskRequest(BaseModel):
    question: str


class MessageOut(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[dict]

    model_config = {"from_attributes": True}


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def ask(
    conversation_id: uuid.UUID,
    body: AskRequest,
    user: CurrentUser,
    conversation_service: Annotated[ConversationService, Depends(get_conversation_service)],
) -> MessageOut:
    # TODO: owner_document_ids should come from a document-access lookup
    # (owned + explicitly shared, per SRS Sec.10) once Document Service lands.
    message = await conversation_service.ask(
        conversation_id=conversation_id, user_id=user.id, question=body.question, owner_document_ids=[]
    )
    return MessageOut.model_validate(message)
