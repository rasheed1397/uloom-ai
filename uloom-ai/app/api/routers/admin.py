"""Resource: /admin/* (Detailed Design Sec.4, SRS FR-009). Admin-only."""
from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users(_admin: AdminUser) -> list[dict]:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")


@router.get("/settings")
async def get_settings_view(_admin: AdminUser) -> dict:
    # e.g. retrieval_top_k, chunk_token_size, similarity_threshold (FR-009)
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not yet implemented")
