import uuid
from datetime import datetime

from pydantic import BaseModel, Field

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

    model_config = {"from_attributes": True}


class UpdateSettingsRequest(BaseModel):
    retrieval_top_k: int | None = Field(default=None, ge=1)
    chunk_token_size: int | None = Field(default=None, ge=1)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
