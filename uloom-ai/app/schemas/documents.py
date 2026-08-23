import uuid
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    filename: str
    mime_type: str
    status: str
    status_detail: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
