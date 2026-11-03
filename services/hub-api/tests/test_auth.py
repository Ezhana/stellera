"""登录 / 刷新 / 登出 / me 的端到端流程。"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import create_engine, create_session_factory
from app.models.user import User
from tests.conftest import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    API_V1,
    VIEWER_PASSWORD,
    VIEWER_USERNAME,
    auth_headers,
    login,
)


def _deactivate_user(settings: Settings, username: str) -> None:
    async def _run() -> None:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                user = (
                    await session.execute(select(User).where(User.username == username))
                ).scalar_one()
                user.is_active = False
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())


def test_login_returns_tokens_and_no_store(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] == 300
    # 登录响应直接带 user（与 /auth/me 同构），前端无需再请求一次 /me。
    user = body["user"]
    assert user["username"] == ADMIN_USERNAME
    assert user["roles"] == ["admin"]
    assert {"object": "/api/v1/auth/me", "action": "^GET$"} in user["permissions"]
    assert response.headers["cache-control"] == "no-store"


def test_login_is_case_and_whitespace_insensitive(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": "  Admin ", "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200


def test_login_with_wrong_password_is_401(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": ADMIN_USERNAME, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.headers["cache-control"] == "no-store"
    assert "Bearer" in response.headers["www-authenticate"]


def test_login_with_unknown_user_is_401(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": "nobody", "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(settings: Settings, client: TestClient) -> None:
    _deactivate_user(settings, VIEWER_USERNAME)

    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": VIEWER_USERNAME, "password": VIEWER_PASSWORD},
    )

    assert response.status_code == 401


def test_oauth2_password_form_token_endpoint(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    # OAuth2 token 端点保持纯 TokenResponse 契约。
    assert "user" not in body
    assert response.headers["cache-control"] == "no-store"


def test_oauth2_token_endpoint_rejects_bad_credentials(client: TestClient) -> None:
    response = client.post(
        f"{API_V1}/auth/token",
        data={"username": ADMIN_USERNAME, "password": "nope"},
    )

    assert response.status_code == 401


def test_me_returns_current_user_and_roles(client: TestClient) -> None:
    pair = login(client)

    response = client.get(f"{API_V1}/auth/me", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == ADMIN_USERNAME
    assert body["email"] == "admin@example.com"
    assert body["is_active"] is True
    assert body["roles"] == ["admin"]
    # 来自 Casbin implicit permissions 的权限清单。
    assert {"object": "/api/v1/auth/me", "action": "^GET$"} in body["permissions"]
    assert {"object": "/api/v1/auth/logout", "action": "^POST$"} in body["permissions"]


def test_me_requires_authentication(client: TestClient) -> None:
    response = client.get(f"{API_V1}/auth/me")

    assert response.status_code == 401
    assert "Bearer" in response.headers["www-authenticate"]


def test_refresh_rotates_token(client: TestClient) -> None:
    first = login(client)

    response = client.post(f"{API_V1}/auth/refresh", json={"refresh_token": first["refresh_token"]})

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    second = response.json()
    assert "user" not in second
    assert second["refresh_token"] != first["refresh_token"]

    me = client.get(f"{API_V1}/auth/me", headers=auth_headers(second["access_token"]))
    assert me.status_code == 200


def test_refresh_replay_revokes_all_user_tokens(client: TestClient) -> None:
    first = login(client)
    rotated = client.post(
        f"{API_V1}/auth/refresh", json={"refresh_token": first["refresh_token"]}
    ).json()

    # 旧 refresh token 再次使用 = 重放，应 401 并吊销该用户全部 refresh token。
    replay = client.post(f"{API_V1}/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401

    after = client.post(f"{API_V1}/auth/refresh", json={"refresh_token": rotated["refresh_token"]})
    assert after.status_code == 401


def test_refresh_with_garbage_token_is_401(client: TestClient) -> None:
    response = client.post(f"{API_V1}/auth/refresh", json={"refresh_token": "not-a-jwt"})

    assert response.status_code == 401


def test_logout_revokes_refresh_tokens(client: TestClient) -> None:
    pair = login(client)

    logout = client.post(f"{API_V1}/auth/logout", headers=auth_headers(pair["access_token"]))
    assert logout.status_code == 204

    refresh = client.post(f"{API_V1}/auth/refresh", json={"refresh_token": pair["refresh_token"]})
    assert refresh.status_code == 401


def test_logout_requires_authentication(client: TestClient) -> None:
    response = client.post(f"{API_V1}/auth/logout")

    assert response.status_code == 401
