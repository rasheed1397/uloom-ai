import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.models.user import User, UserRole


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict[str, str]:
    register = await client.post(
        "/auth/register", json={"email": "doc-user@example.com", "password": "hunter2hunter2"}
    )
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def other_user_headers(client: AsyncClient) -> dict[str, str]:
    register = await client.post(
        "/auth/register", json={"email": "other-user@example.com", "password": "hunter2hunter2"}
    )
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(client: AsyncClient, db_session: AsyncSession) -> dict[str, str]:
    register = await client.post(
        "/auth/register", json={"email": "doc-admin@example.com", "password": "hunter2hunter2"}
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


async def _upload_empty_document(client: AsyncClient, headers: dict[str, str]) -> dict:
    # Empty content means extract_text/chunk_segments produce nothing, so
    # DocumentService.process() (which the test's in-process ASGI transport
    # runs synchronously as part of the request, unlike a real deployed
    # server) never calls the embedding provider - keeps this test hermetic,
    # no live Gemini call or API key needed.
    response = await client.post(
        "/documents", headers=headers, files={"file": ("empty.txt", b"", "text/plain")}
    )
    assert response.status_code == 202
    return response.json()


async def test_document_endpoints_require_auth(client: AsyncClient):
    document_id = uuid.uuid4()
    assert (await client.post("/documents", files={"file": ("a.txt", b"x", "text/plain")})).status_code == 401
    assert (await client.get("/documents")).status_code == 401
    assert (await client.get(f"/documents/{document_id}")).status_code == 401
    assert (await client.delete(f"/documents/{document_id}")).status_code == 401


async def test_upload_document_rejects_unsupported_mime_type(
    client: AsyncClient, auth_headers: dict[str, str]
):
    response = await client.post(
        "/documents", headers=auth_headers, files={"file": ("a.zip", b"data", "application/zip")}
    )
    assert response.status_code == 415


async def test_upload_list_get_delete_document_round_trip(client: AsyncClient, auth_headers: dict[str, str]):
    uploaded = await _upload_empty_document(client, auth_headers)
    document_id = uploaded["id"]
    assert uploaded["status"] == "uploaded"

    listed = await client.get("/documents", headers=auth_headers)
    assert listed.status_code == 200
    assert document_id in [d["id"] for d in listed.json()]

    fetched = await client.get(f"/documents/{document_id}", headers=auth_headers)
    assert fetched.status_code == 200
    # Empty upload has nothing to chunk/embed, so indexing completes
    # (synchronously, in this test's ASGI transport) straight to indexed.
    assert fetched.json()["status"] == "indexed"

    deleted = await client.delete(f"/documents/{document_id}", headers=auth_headers)
    assert deleted.status_code == 204

    after_delete = await client.get(f"/documents/{document_id}", headers=auth_headers)
    assert after_delete.status_code == 404


async def test_document_endpoints_404_for_a_document_you_do_not_own(
    client: AsyncClient, auth_headers: dict[str, str], other_user_headers: dict[str, str]
):
    uploaded = await _upload_empty_document(client, auth_headers)
    document_id = uploaded["id"]

    assert (await client.get(f"/documents/{document_id}", headers=other_user_headers)).status_code == 404
    assert (await client.delete(f"/documents/{document_id}", headers=other_user_headers)).status_code == 404


async def test_admin_endpoints_reject_standard_user(client: AsyncClient, auth_headers: dict[str, str]):
    assert (await client.get("/admin/users", headers=auth_headers)).status_code == 403
    assert (await client.get("/admin/documents", headers=auth_headers)).status_code == 403
    assert (await client.get("/admin/settings", headers=auth_headers)).status_code == 403


async def test_admin_can_list_and_disable_users(
    client: AsyncClient, admin_headers: dict[str, str], auth_headers: dict[str, str]
):
    listed = await client.get("/admin/users", headers=admin_headers)
    assert listed.status_code == 200
    emails = [u["email"] for u in listed.json()]
    assert "doc-user@example.com" in emails

    target = next(u for u in listed.json() if u["email"] == "doc-user@example.com")
    patched = await client.patch(
        f"/admin/users/{target['id']}", headers=admin_headers, json={"is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    # The disabled user's existing token is rejected on the very next request.
    assert (await client.get("/documents", headers=auth_headers)).status_code == 401


async def test_admin_update_user_404s_for_unknown_user(client: AsyncClient, admin_headers: dict[str, str]):
    response = await client.patch(
        f"/admin/users/{uuid.uuid4()}", headers=admin_headers, json={"is_active": False}
    )
    assert response.status_code == 404


async def test_admin_can_list_and_delete_any_users_document(
    client: AsyncClient, admin_headers: dict[str, str], auth_headers: dict[str, str]
):
    uploaded = await _upload_empty_document(client, auth_headers)
    document_id = uploaded["id"]

    listed = await client.get("/admin/documents", headers=admin_headers)
    assert listed.status_code == 200
    assert document_id in [d["id"] for d in listed.json()]

    deleted = await client.delete(f"/admin/documents/{document_id}", headers=admin_headers)
    assert deleted.status_code == 204
    assert (await client.get(f"/documents/{document_id}", headers=auth_headers)).status_code == 404


async def test_admin_delete_document_404s_for_unknown_document(
    client: AsyncClient, admin_headers: dict[str, str]
):
    response = await client.delete(f"/admin/documents/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


async def test_admin_settings_view_reflects_config(client: AsyncClient, admin_headers: dict[str, str]):
    response = await client.get("/admin/settings", headers=admin_headers)
    assert response.status_code == 200
    assert response.json() == {
        "retrieval_top_k": 5,
        "chunk_token_size": 512,
        "similarity_threshold": 0.7,
        "retention_days": 90,
    }


async def test_admin_can_update_settings_and_it_takes_effect_without_a_deployment(
    client: AsyncClient, admin_headers: dict[str, str]
):
    updated = await client.patch(
        "/admin/settings", headers=admin_headers, json={"retrieval_top_k": 3, "similarity_threshold": 0.5}
    )
    assert updated.status_code == 200
    assert updated.json() == {
        "retrieval_top_k": 3,
        "chunk_token_size": 512,  # untouched field keeps its previous value
        "similarity_threshold": 0.5,
        "retention_days": 90,  # untouched field keeps its previous value
    }

    # FR-009: reflected immediately on the next request, no redeploy/restart.
    fetched = await client.get("/admin/settings", headers=admin_headers)
    assert fetched.json() == updated.json()


async def test_admin_update_settings_rejects_invalid_values(
    client: AsyncClient, admin_headers: dict[str, str]
):
    response = await client.patch(
        "/admin/settings", headers=admin_headers, json={"similarity_threshold": 1.5}
    )
    assert response.status_code == 422
