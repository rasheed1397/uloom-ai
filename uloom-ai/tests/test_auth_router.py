from httpx import AsyncClient


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
