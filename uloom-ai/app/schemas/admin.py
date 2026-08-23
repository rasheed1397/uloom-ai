import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.user import UserRole


class AdminUserOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateUserRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class SettingsOut(BaseModel):
    retrieval_top_k: int
    chunk_token_size: int
    similarity_threshold: float
