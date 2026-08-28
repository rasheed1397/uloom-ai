from httpx import AsyncClient

from app.schemas.auth import UpdateProfileRequest


async def test_register_then_me_round_trip(client: AsyncClient):
    register = await client.post(
        "/auth/register", json={"email": "roundtrip@example.com", "password": "hunter2hunter2"}
    )
    assert register.status_code == 201
    token = register.json()["access_token"]

    me = await client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "roundtrip@example.com"
    assert me.json()["role"] == "standard"


async def test_register_rejects_duplicate_email(client: AsyncClient):
    payload = {"email": "dupe@example.com", "password": "hunter2hunter2"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_returns_token_for_correct_credentials(client: AsyncClient):
    await client.post("/auth/register", json={"email": "login@example.com", "password": "hunter2hunter2"})

    login = await client.post(
        "/auth/login", json={"email": "login@example.com", "password": "hunter2hunter2"}
    )

    assert login.status_code == 200
    assert "access_token" in login.json()


async def test_login_rejects_wrong_password(client: AsyncClient):
    await client.post("/auth/register", json={"email": "login2@example.com", "password": "hunter2hunter2"})

    login = await client.post("/auth/login", json={"email": "login2@example.com", "password": "wrong"})

    assert login.status_code == 401


async def test_me_requires_authentication(client: AsyncClient):
    response = await client.get("/users/me")
    assert response.status_code == 401


async def test_update_me_changes_email(client: AsyncClient):
    register = await client.post(
        "/auth/register", json={"email": "before@example.com", "password": "hunter2hunter2"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = await client.patch("/users/me", headers=headers, json={"email": "after@example.com"})

    assert response.status_code == 200
    assert response.json()["email"] == "after@example.com"

    me = await client.get("/users/me", headers=headers)
    assert me.json()["email"] == "after@example.com"


async def test_update_me_changes_password(client: AsyncClient):
    register = await client.post(
        "/auth/register", json={"email": "changepw@example.com", "password": "hunter2hunter2"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = await client.patch("/users/me", headers=headers, json={"password": "newpassword123"})
    assert response.status_code == 200

    old_login = await client.post(
        "/auth/login", json={"email": "changepw@example.com", "password": "hunter2hunter2"}
    )
    assert old_login.status_code == 401

    new_login = await client.post(
        "/auth/login", json={"email": "changepw@example.com", "password": "newpassword123"}
    )
    assert new_login.status_code == 200


async def test_update_me_rejects_email_already_taken(client: AsyncClient):
    await client.post("/auth/register", json={"email": "taken@example.com", "password": "hunter2hunter2"})
    register = await client.post(
        "/auth/register", json={"email": "wants-taken@example.com", "password": "hunter2hunter2"}
    )
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}

    response = await client.patch("/users/me", headers=headers, json={"email": "taken@example.com"})

    assert response.status_code == 409


async def test_update_me_cannot_change_role():
    # Schema-level guarantee: role isn't even an accepted field, so there's
    # no request shape that could self-promote (FR-002 - role changes are
    # Administrator-only, via PATCH /admin/users/{id}).
    assert "role" not in UpdateProfileRequest.model_fields


async def test_update_me_requires_authentication(client: AsyncClient):
    response = await client.patch("/users/me", json={"email": "nope@example.com"})
    assert response.status_code == 401
