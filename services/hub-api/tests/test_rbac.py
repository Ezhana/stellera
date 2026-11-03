"""RBAC：401/403 区分、角色继承、公开注册与权限清单。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.middleware.rbac import normalize_path
from app.rbac.enforcer import EnforcerGuard
from tests.conftest import (
    ADMIN_USERNAME,
    API_V1,
    ENGINEER_PASSWORD,
    ENGINEER_USERNAME,
    ENTERPRISE_PASSWORD,
    ENTERPRISE_USERNAME,
    MEMBER_PASSWORD,
    MEMBER_USERNAME,
    auth_headers,
    login,
)

BUSINESS_PERMISSIONS = {
    ("/api/v1/auth/me", "^GET$"),
    ("/api/v1/auth/logout", "^POST$"),
    ("/api/v1/wallet", "^GET$"),
    ("/api/v1/wallet/transactions", "^GET$"),
    ("/api/v1/wallet/redeem", "^POST$"),
    ("/api/v1/fde/orders", "^GET$"),
    ("/api/v1/fde/orders/*", "^GET$"),
    ("/api/v1/fde/orders", "^POST$"),
    ("/api/v1/fde/orders/*/cancel", "^POST$"),
    ("/api/v1/fde/orders/*/logs", "^POST$"),
    ("/api/v1/fde/orders/*/applications", "^POST$"),
    ("/api/v1/fde/applications/mine", "^GET$"),
    ("/api/v1/fde/applications/received", "^GET$"),
    ("/api/v1/fde/applications/*/approve", "^POST$"),
    ("/api/v1/fde/applications/*/reject", "^POST$"),
    ("/api/v1/fde/applications/*/withdraw", "^POST$"),
    ("/api/v1/profile", "^GET$"),
    ("/api/v1/profile", "^PATCH$"),
    ("/api/v1/profile/certification-applications", "^GET$"),
    ("/api/v1/profile/certification-applications", "^POST$"),
    ("/api/v1/profiles/*", "^GET$"),
}

# 用真实 HTTP 方法与代表性路径验证 Casbin 矩阵（策略 action 是 ^GET$ 形式的正则）。
BUSINESS_ENDPOINTS = {
    ("GET", "/api/v1/auth/me"),
    ("POST", "/api/v1/auth/logout"),
    ("GET", "/api/v1/wallet"),
    ("GET", "/api/v1/wallet/transactions"),
    ("POST", "/api/v1/wallet/redeem"),
    ("GET", "/api/v1/fde/orders"),
    ("GET", "/api/v1/fde/orders/1"),
    ("POST", "/api/v1/fde/orders"),
    ("POST", "/api/v1/fde/orders/1/cancel"),
    ("POST", "/api/v1/fde/orders/1/logs"),
    ("POST", "/api/v1/fde/orders/1/applications"),
    ("GET", "/api/v1/fde/applications/mine"),
    ("GET", "/api/v1/fde/applications/received"),
    ("POST", "/api/v1/fde/applications/1/approve"),
    ("POST", "/api/v1/fde/applications/1/reject"),
    ("POST", "/api/v1/fde/applications/1/withdraw"),
    ("GET", "/api/v1/profile"),
    ("PATCH", "/api/v1/profile"),
    ("GET", "/api/v1/profile/certification-applications"),
    ("POST", "/api/v1/profile/certification-applications"),
    ("GET", "/api/v1/profiles/1"),
}


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
    pair = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    # member 没有管理端通配权限：已认证但无权限。
    response = client.get(f"{API_V1}/admin/ping", headers=auth_headers(pair["access_token"]))

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


def test_anonymous_can_register_but_not_use_business_api(app, client: TestClient) -> None:
    guard: EnforcerGuard = app.state.enforcer_guard

    assert guard.enforce("anonymous", "/api/v1/auth/register", "POST") is True
    assert guard.enforce("anonymous", "/api/v1/auth/login", "POST") is True
    assert guard.enforce("anonymous", "/api/v1/auth/me", "GET") is False
    assert guard.enforce("anonymous", "/api/v1/wallet", "GET") is False
    assert guard.enforce("anonymous", "/api/v1/fde/orders", "GET") is False

    response = client.post(
        f"{API_V1}/auth/register",
        json={
            "username": "rbac_register",
            "email": "rbac_register@example.com",
            "password": "secret123",
        },
    )
    assert response.status_code == 201


def test_role_hierarchy_matches_expected_matrix(app, client: TestClient) -> None:
    # client fixture 用于触发 lifespan（把 PG/SQLite 中的 RBAC 投影到 enforcer）。
    guard: EnforcerGuard = app.state.enforcer_guard

    # 角色树：authenticated -> member -> realname / enterprise / engineer / admin。
    for role_name in ("authenticated", "member", "realname", "enterprise", "engineer", "admin"):
        assert guard.enforce(f"role:{role_name}", "/api/v1/auth/me", "GET") is True
    for retired in ("viewer", "operator"):
        assert guard.enforce(f"role:{retired}", "/api/v1/auth/me", "GET") is False

    # authenticated 拥有全部业务端点（服务层再做归属判断）。
    for method, path in BUSINESS_ENDPOINTS:
        assert guard.enforce("role:authenticated", path, method) is True, (method, path)
        assert guard.enforce("role:member", path, method) is True, (method, path)
        assert guard.enforce("role:realname", path, method) is True, (method, path)
        assert guard.enforce("role:enterprise", path, method) is True, (method, path)
        assert guard.enforce("role:engineer", path, method) is True, (method, path)

    # 已移除的旧认领 / 完成端点不再有任何策略（admin 通配除外）。
    assert guard.enforce("role:authenticated", "/api/v1/fde/orders/1/claim", "POST") is False
    assert guard.enforce("role:authenticated", "/api/v1/fde/orders/1/complete", "POST") is False

    # 管理端：admin 通配；其它角色即使继承了全部业务端点也进不去管理端。
    assert guard.enforce("role:admin", "/api/v1/admin/users", "GET") is True
    assert guard.enforce("role:admin", "/api/v1/admin/certification-applications", "GET") is True
    assert guard.enforce("role:realname", "/api/v1/admin/users", "GET") is False
    assert guard.enforce("role:admin", "/api/v1/fde/orders", "DELETE") is True
    assert guard.enforce("role:member", "/api/v1/admin/users", "GET") is False
    assert guard.enforce("role:enterprise", "/api/v1/admin/users", "GET") is False


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (MEMBER_USERNAME, MEMBER_PASSWORD),
        (ENGINEER_USERNAME, ENGINEER_PASSWORD),
        (ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD),
    ],
)
def test_all_logged_in_roles_can_publish_and_apply(
    client: TestClient, username: str, password: str
) -> None:
    pair = login(client, username, password)

    # 任何登录用户都可以发布订单（余额足够）。
    published = client.post(
        f"{API_V1}/fde/orders",
        headers=auth_headers(pair["access_token"]),
        json={
            "title": "RBAC 矩阵验证订单",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 3,
            "price_cents": 10_000,
        },
    )
    assert published.status_code == 201, published.text

    # 任何登录用户都可以申请别人的订单（服务层再判归属与状态）。
    admin = login(client)
    assert (
        client.post(
            f"{API_V1}/fde/orders/{published.json()['id']}/applications",
            headers=auth_headers(admin["access_token"]),
            json={"type": "accept"},
        ).status_code
        == 201
    )

    # 工作日志 / 审批权限由服务层判断，Casbin 不按角色拦截。
    assert client.post(
        f"{API_V1}/fde/orders/{published.json()['id']}/logs",
        headers=auth_headers(pair["access_token"]),
        json={"content": "服务层会拒绝"},
    ).status_code in {403, 409}


def test_admin_can_reach_admin_namespace(client: TestClient) -> None:
    # 未注册的管理端路径：Casbin 放行后由路由返回 404，而不是 401/403。
    pair = login(client)
    response = client.get(f"{API_V1}/admin/ping", headers=auth_headers(pair["access_token"]))

    assert response.status_code == 404


def test_admin_login_username_constant_is_admin() -> None:
    # 防呆：conftest 默认管理员用户名与 seed 默认值一致。
    assert ADMIN_USERNAME == "admin"


def test_me_permissions_follow_role_hierarchy(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    admin = login(client)

    member_me = client.get(f"{API_V1}/auth/me", headers=auth_headers(member["access_token"])).json()
    member_permissions = {(item["object"], item["action"]) for item in member_me["permissions"]}
    assert member_me["roles"] == ["member"]
    assert member_permissions == BUSINESS_PERMISSIONS

    admin_me = client.get(f"{API_V1}/auth/me", headers=auth_headers(admin["access_token"])).json()
    admin_permissions = {(item["object"], item["action"]) for item in admin_me["permissions"]}
    assert admin_me["roles"] == ["admin"]
    # 21 条业务权限 + admin 通配 = 22 条。
    assert len(admin_permissions) == 22
    assert len(BUSINESS_PERMISSIONS) == 21
    assert ("/api/v1/*", "^(GET|POST|PUT|PATCH|DELETE)$") in admin_permissions
    assert BUSINESS_PERMISSIONS <= admin_permissions
    # 历史角色 / 认领完成端点不再出现。
    assert ("/api/v1/fde/orders/*/claim", "^POST$") not in admin_permissions
    assert ("/api/v1/fde/orders/*/complete", "^POST$") not in admin_permissions


def test_login_user_matches_me(client: TestClient) -> None:
    pair = login(client)

    me = client.get(f"{API_V1}/auth/me", headers=auth_headers(pair["access_token"])).json()
    assert pair["user"] == me
