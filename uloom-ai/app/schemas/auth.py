import uuid

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    # Deliberately no `role` field: role changes are Administrator-driven
    # only (FR-002 acceptance criteria), via PATCH /admin/users/{id}. Adding
    # it here would let a user promote themselves.
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
