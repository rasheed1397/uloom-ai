"""Resource: /users/me (Detailed Design Sec.4, SRS FR-002)."""
from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.auth import UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def read_current_user(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
