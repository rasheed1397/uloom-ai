"""Resource: /auth/register, /auth/login (Detailed Design Sec.4, SRS FR-001)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_auth_service
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.auth_service import (
    AuthService,
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenResponse:
    try:
        _, token = await auth_service.register(body.email, body.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, auth_service: Annotated[AuthService, Depends(get_auth_service)]
) -> TokenResponse:
    try:
        _, token = await auth_service.login(body.email, body.password)
    except InvalidCredentialsError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials") from None
    return TokenResponse(access_token=token)
