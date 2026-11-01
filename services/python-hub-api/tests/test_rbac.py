"""RBAC：401/403 区分、角色继承、路径归一化与 OPTIONS 放行。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.middleware.rbac import normalize_path
from app.rbac.enforcer import EnforcerGuard
from tests.conftest import (
    ADMIN_USERNAME,
    API_V1,
    OPERATOR_PASSWORD,
    OPERATOR_USERNAME,
    VIEWER_PASSWORD,
    VIEWER_USERNAME,
    auth_headers,
    login,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("/api/v1/auth/me", "/api/v1/auth/me"),
        ("/api/v1/auth/me/", "/api/v1/auth/me"),
        ("//api//v1//auth/me", "/api/v1/auth/me"),
        ("/api/v1/auth/me///", "/api/v1/auth/me"),
        ("/", "/"),
        ("health", "/health"),
    ],
)
def test_normalize_path(raw: str, expected: str) -> None:
    assert normalize_path(raw) == expected


def test_unauthenticated_gets_401(client: TestClient) -> None:
    response = client.get(f"{API_V1}/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_authenticated_but_forbidden_gets_403(client: TestClient) -> None:
    pair = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    # viewer 只有读权限；对业务路径发 POST 已认证但无权限。
    response = client.post(f"{API_V1}/wallet/balance", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_double_slash_path_cannot_bypass_rbac(client: TestClient) -> None:
    # 归一化后 /api/v1/auth/me 对匿名主体仍是受保护路径，应返回 401 而不是 404。
    response = client.get("/api//v1/auth/me")

    assert response.status_code == 401


def test_trailing_slash_still_uses_normalized_policy(client: TestClient) -> None:
    pair = login(client)

    response = client.get(f"{API_V1}/auth/me/", headers=auth_headers(pair["access_token"]))

    # 归一生效（未认证会被 401 拦住）；Starlette 随后按 redirect_slashes 处理。
    assert response.status_code in {200, 307}


def test_options_is_not_enforced(client: TestClient) -> None:
    response = client.options(f"{API_V1}/auth/me")

    assert response.status_code != 401
    assert response.status_code != 403


def test_cors_preflight_from_known_origin(client: TestClient) -> None:
    response = client.options(
        f"{API_V1}/auth/me",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_role_hierarchy_matches_expected_matrix(app, client: TestClient) -> None:
    # client fixture 用于触发 lifespan（把 PG/SQLite 中的 RBAC 投影到 enforcer）。
    guard: EnforcerGuard = app.state.enforcer_guard

    # 匿名只能访问公开端点
    assert guard.enforce("anonymous", "/api/v1/auth/login", "POST") is True
    assert guard.enforce("anonymous", "/api/v1/auth/me", "GET") is False

    # viewer 只读，且权限按模块收窄，不能读管理端命名空间
    assert guard.enforce("role:viewer", "/api/v1/wallet/balance", "GET") is True
    assert guard.enforce("role:viewer", "/api/v1/wallet/balance", "POST") is False
    assert guard.enforce("role:viewer", "/api/v1/admin/ping", "GET") is False

    # operator 继承 viewer 的读权限，并额外可写订单/广场
    assert guard.enforce("role:operator", "/api/v1/wallet/balance", "GET") is True
    assert guard.enforce("role:operator", "/api/v1/orders", "POST") is True
    assert guard.enforce("role:operator", "/api/v1/orders", "DELETE") is False
    assert guard.enforce("role:operator", "/api/v1/admin/ping", "GET") is False

    # admin 继承 operator，并且拥有全部方法（管理端仍无路由，放行后 404）
    assert guard.enforce("role:admin", "/api/v1/admin/users", "GET") is True
    assert guard.enforce("role:admin", "/api/v1/wallet/balance", "DELETE") is True

    # 所有登录用户都被归入 authenticated（可访问 /auth/me 与 /auth/logout）
    assert guard.enforce("role:authenticated", "/api/v1/auth/me", "GET") is True
    assert guard.enforce("role:authenticated", "/api/v1/auth/logout", "POST") is True


def test_admin_can_reach_admin_namespace(client: TestClient, app) -> None:
    # 管理端还没有具体端点：Casbin 放行后由路由返回 404，而不是 401/403。
    pair = login(client)
    response = client.get(f"{API_V1}/admin/ping", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 404


def test_operator_cannot_delete_admin_resource(client: TestClient) -> None:
    pair = login(client, OPERATOR_USERNAME, OPERATOR_PASSWORD)
    response = client.delete(f"{API_V1}/admin/ping", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 403


def test_viewer_cannot_read_admin_namespace(client: TestClient) -> None:
    pair = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    response = client.get(f"{API_V1}/admin/ping", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 403


def test_admin_login_username_constant_is_admin() -> None:
    # 防呆：conftest 默认管理员用户名与 seed 默认值一致。
    assert ADMIN_USERNAME == "admin"


def test_me_permissions_follow_role_hierarchy(client: TestClient) -> None:
    pair = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    me = client.get(f"{API_V1}/auth/me", headers=auth_headers(pair["access_token"])).json()
    permissions = {(item["object"], item["action"]) for item in me["permissions"]}

    # viewer 继承 authenticated 的两个端点权限 + 自己的模块只读权限。
    assert ("/api/v1/auth/me", "^GET$") in permissions
    assert ("/api/v1/auth/logout", "^POST$") in permissions
    assert ("/api/v1/wallet/*", "^GET$") in permissions
    assert ("/api/v1/orders", "^GET$") in permissions
    assert ("/api/v1/plaza/*", "^GET$") in permissions
    assert ("/api/v1/*", "^(POST|PUT|PATCH)$") not in permissions


def test_login_user_matches_me(client: TestClient) -> None:
    pair = login(client)

    me = client.get(f"{API_V1}/auth/me", headers=auth_headers(pair["access_token"])).json()
    assert pair["user"] == me
