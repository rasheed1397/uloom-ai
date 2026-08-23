import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.models.user import User, UserRole


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    register = await client.post(
        "/auth/register", json={"email": "stub-user@example.com", "password": "hunter2hunter2"}
    )
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    register = await client.post(
        "/auth/register", json={"email": "stub-admin@example.com", "password": "hunter2hunter2"}
    )
    token = register.json()["access_token"]
    user = await db_session.get(User, uuid.UUID(_decode_sub(token)))
    assert user is not None
    user.role = UserRole.ADMIN
    await db_session.commit()
    return {"Authorization": f"Bearer {token}"}


def _decode_sub(token: str) -> str:
    payload = decode_access_token(token)
    assert payload is not None
    return payload["sub"]


async def test_document_endpoints_require_auth(client: AsyncClient):
    document_id = uuid.uuid4()
    assert (await client.post("/documents", json={})).status_code == 401
    assert (await client.get("/documents")).status_code == 401
    assert (await client.get(f"/documents/{document_id}")).status_code == 401
    assert (await client.delete(f"/documents/{document_id}")).status_code == 401


async def test_document_endpoints_are_not_yet_implemented(client: AsyncClient, auth_headers: dict[str, str]):
    document_id = uuid.uuid4()
    assert (await client.post("/documents", json={}, headers=auth_headers)).status_code == 501
    assert (await client.get("/documents", headers=auth_headers)).status_code == 501
    assert (await client.get(f"/documents/{document_id}", headers=auth_headers)).status_code == 501
    assert (await client.delete(f"/documents/{document_id}", headers=auth_headers)).status_code == 501


async def test_admin_endpoints_reject_standard_user(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/admin/users", headers=auth_headers)
    assert response.status_code == 403


async def test_admin_endpoints_are_not_yet_implemented_for_admins(
    client: AsyncClient, admin_headers: dict[str, str]
):
    assert (await client.get("/admin/users", headers=admin_headers)).status_code == 501
    assert (await client.get("/admin/settings", headers=admin_headers)).status_code == 501
