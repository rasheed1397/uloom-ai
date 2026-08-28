"""Resource: /users/me (Detailed Design Sec.4, SRS FR-002)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentUser, get_auth_service
from app.schemas.auth import UpdateProfileRequest, UserOut
from app.services.auth_service import AuthService, EmailAlreadyRegisteredError

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_current_user(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me", response_model=UserOut)
async def update_current_user(
    body: UpdateProfileRequest,
    user: CurrentUser,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserOut:
    try:
        updated = await auth_service.update_profile(user, email=body.email, password=body.password)
    except EmailAlreadyRegisteredError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered") from None
    return UserOut.model_validate(updated)
