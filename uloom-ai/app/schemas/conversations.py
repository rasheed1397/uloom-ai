import uuid
from datetime import datetime

from pydantic import BaseModel


class CreateConversationRequest(BaseModel):
    title: str | None = None


class ConversationOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
