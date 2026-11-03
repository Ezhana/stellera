"""管理后台端到端测试：用户 / 角色目录 / 兑换码 / 系统设置。

仅 admin 可用；非管理员由 Casbin 拦截返回 403。演示数据：5 个用户、3 个兑换码。
"""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import create_engine, create_session_factory
from app.models.base import utcnow
from app.models.redeem import RedeemCode
from app.models.user import User
from app.services import admin as admin_service
from app.services.admin import AdminConflictError
from tests.conftest import (
    API_V1,
    OPERATOR_PASSWORD,
    OPERATOR_USERNAME,
    VIEWER_PASSWORD,
    VIEWER_USERNAME,
    auth_headers,
    login,
)

ADMIN = f"{API_V1}/admin"
FDE = f"{API_V1}/fde"

USER_FIELDS = {
    "id",
    "username",
    "email",
    "full_name",
    "is_active",
    "roles",
    "balance_cents",
    "created_at",
}

CODE_FIELDS = {
    "id",
    "code",
    "amount_cents",
    "status",
    "batch_no",
    "note",
    "is_expired",
    "used_by",
    "used_at",
    "expires_at",
    "created_at",
}


# ---------- 测试辅助 ----------


def _headers(pair: dict) -> dict[str, str]:
    return auth_headers(pair["access_token"])


def _list_users(client: TestClient, pair: dict, **params: str | int) -> dict:
    response = client.get(f"{ADMIN}/users", params=params, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _find_user(items: list[dict], username: str) -> dict:
    for item in items:
        if item["username"] == username:
            return item
    raise AssertionError(f"未找到用户 {username}")


def _list_codes(client: TestClient, pair: dict, **params: str | int) -> dict:
    response = client.get(f"{ADMIN}/redeem-codes", params=params, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _create_codes(
    client: TestClient,
    pair: dict,
    *,
    amount_cents: int = 50_000,
    quantity: int = 1,
    expires_in_days: int | None = 30,
    note: str | None = "测试批次",
) -> dict:
    response = client.post(
        f"{ADMIN}/redeem-codes",
        headers=_headers(pair),
        json={
            "amount_cents": amount_cents,
            "quantity": quantity,
            "expires_in_days": expires_in_days,
            "note": note,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _setup_code(
    settings: Settings,
    *,
    code: str,
    status: str = "disabled",
    expired: bool = False,
) -> None:
    async def _run() -> None:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                session.add(
                    RedeemCode(
                        code=code,
                        amount_cents=10_000,
                        status=status,
                        batch_no="RDM-TEST",
                        note=None,
                        created_by_id=None,
                        used_by_id=None,
                        used_at=None,
                        expires_at=utcnow() - timedelta(days=1) if expired else None,
                        created_at=utcnow(),
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())


# ---------- 权限 ----------


def test_admin_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(f"{ADMIN}/users").status_code == 401
    assert client.get(f"{ADMIN}/settings").status_code == 401
    assert client.post(f"{ADMIN}/redeem-codes", json={}).status_code == 401


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (VIEWER_USERNAME, VIEWER_PASSWORD),
        (OPERATOR_USERNAME, OPERATOR_PASSWORD),
    ],
)
def test_non_admin_roles_cannot_access_admin(
    client: TestClient, username: str, password: str
) -> None:
    pair = login(client, username, password)

    for path in ("/users", "/roles", "/redeem-codes", "/settings"):
        assert client.get(f"{ADMIN}{path}", headers=_headers(pair)).status_code == 403
    assert (
        client.post(
            f"{ADMIN}/redeem-codes",
            headers=_headers(pair),
            json={"amount_cents": 1000, "quantity": 1},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"{ADMIN}/users/1", headers=_headers(pair), json={"is_active": False}
        ).status_code
        == 403
    )


# ---------- 用户 ----------


def test_list_users_includes_roles_and_balance(client: TestClient) -> None:
    admin = login(client)

    body = _list_users(client, admin, page_size=100)

    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 5
    assert [item["username"] for item in body["items"]] == [
        "admin",
        "operator",
        "viewer",
        "enterprise",
        "engineer",
    ]
    assert set(body["items"][0]) == USER_FIELDS

    expected_balances = {
        "admin": 300_000_000,
        "operator": 200_000,
        "viewer": 150_000,
        "enterprise": 212_300_000,
        "engineer": 15_700_000,
    }
    expected_roles = {
        "admin": ["admin"],
        "operator": ["operator"],
        "viewer": ["viewer"],
        "enterprise": ["enterprise"],
        "engineer": ["engineer"],
    }
    for item in body["items"]:
        assert item["balance_cents"] == expected_balances[item["username"]]
        assert item["roles"] == expected_roles[item["username"]]
        assert item["is_active"] is True
        assert item["created_at"]
    assert _find_user(body["items"], "enterprise")["full_name"] == "企业（演示）"


def test_list_users_search_filter_and_pagination(client: TestClient) -> None:
    admin = login(client)

    assert _list_users(client, admin, q="viewer")["total"] == 1
    assert _list_users(client, admin, q="演示")["total"] == 4
    assert _list_users(client, admin, q="example.com")["total"] == 5
    assert _list_users(client, admin, role="admin")["total"] == 1
    assert _list_users(client, admin, role="engineer")["total"] == 1
    assert _list_users(client, admin, role="nonexistent")["total"] == 0

    page1 = _list_users(client, admin, page=1, page_size=2)
    page2 = _list_users(client, admin, page=2, page_size=2)
    page3 = _list_users(client, admin, page=3, page_size=2)
    assert page1["total"] == 5
    assert [item["id"] for item in page1["items"]] == [1, 2]
    assert [item["id"] for item in page2["items"]] == [3, 4]
    assert [item["id"] for item in page3["items"]] == [5]


def test_roles_catalog_excludes_authenticated(client: TestClient) -> None:
    admin = login(client)

    response = client.get(f"{ADMIN}/roles", headers=_headers(admin))

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["name"] for item in items] == [
        "admin",
        "operator",
        "viewer",
        "enterprise",
        "engineer",
    ]
    assert all(item["description"] for item in items)


def test_disable_user_blocks_login(client: TestClient) -> None:
    admin = login(client)
    viewer = _find_user(_list_users(client, admin)["items"], "viewer")

    disabled = client.patch(
        f"{ADMIN}/users/{viewer['id']}",
        headers=_headers(admin),
        json={"is_active": False},
    )

    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False
    assert disabled.json()["roles"] == ["viewer"]
    assert disabled.json()["balance_cents"] == 150_000

    response = client.post(
        f"{API_V1}/auth/login",
        json={"username": VIEWER_USERNAME, "password": VIEWER_PASSWORD},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "用户已被禁用"

    # 重新启用后可以正常登录。
    enabled = client.patch(
        f"{ADMIN}/users/{viewer['id']}",
        headers=_headers(admin),
        json={"is_active": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["is_active"] is True
    login(client, VIEWER_USERNAME, VIEWER_PASSWORD)


def test_role_change_takes_effect_immediately(client: TestClient) -> None:
    admin = login(client)
    viewer_pair = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    viewer = _find_user(_list_users(client, admin)["items"], "viewer")
    enterprise = login(client)

    changed = client.patch(
        f"{ADMIN}/users/{viewer['id']}",
        headers=_headers(admin),
        json={"roles": ["viewer", "engineer"]},
    )
    assert changed.status_code == 200
    assert changed.json()["roles"] == ["viewer", "engineer"]

    # 已登录的 viewer 不重新登录也能认领订单（Casbin 投影已即时刷新）。
    order = client.post(
        f"{FDE}/orders",
        headers=_headers(enterprise),
        json={
            "title": "角色变更后认领",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 3,
            "price_cents": 100_000,
        },
    )
    assert order.status_code == 201, order.text
    claimed = client.post(f"{FDE}/orders/{order.json()['id']}/claim", headers=_headers(viewer_pair))
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["engineer"]["display_name"] == "访客（演示）"

    me = client.get(f"{API_V1}/auth/me", headers=_headers(viewer_pair)).json()
    assert set(me["roles"]) == {"viewer", "engineer"}


def test_update_user_validation_and_not_found(client: TestClient) -> None:
    admin = login(client)
    viewer = _find_user(_list_users(client, admin)["items"], "viewer")

    invalid = client.patch(
        f"{ADMIN}/users/{viewer['id']}",
        headers=_headers(admin),
        json={"roles": ["superuser"]},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "存在无效角色"

    missing = client.patch(
        f"{ADMIN}/users/999999", headers=_headers(admin), json={"is_active": False}
    )
    assert missing.status_code == 404


def test_cannot_disable_or_demote_self(client: TestClient) -> None:
    admin = login(client)
    admin_id = admin["user"]["id"]

    disabled = client.patch(
        f"{ADMIN}/users/{admin_id}", headers=_headers(admin), json={"is_active": False}
    )
    assert disabled.status_code == 409
    assert disabled.json()["detail"] == "不能停用当前登录账号"

    demoted = client.patch(
        f"{ADMIN}/users/{admin_id}", headers=_headers(admin), json={"roles": ["operator"]}
    )
    assert demoted.status_code == 409
    assert demoted.json()["detail"] == "不能移除自己的管理员角色"


def test_cannot_remove_last_admin(settings: Settings, client: TestClient) -> None:
    """端点层会先拦截非管理员，这里直接验证服务层的“最后管理员”兜底保护。"""

    async def _run() -> None:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                admin = (
                    await session.execute(select(User).where(User.username == "admin"))
                ).scalar_one()
                viewer = (
                    await session.execute(select(User).where(User.username == "viewer"))
                ).scalar_one()
                with pytest.raises(AdminConflictError, match="不能移除最后一个管理员"):
                    await admin_service.update_user(
                        session,
                        actor_id=viewer.id,
                        user_id=admin.id,
                        roles=["operator"],
                    )
        finally:
            await engine.dispose()

    asyncio.run(_run())


# ---------- 兑换码 ----------


def test_create_redeem_codes_batch(client: TestClient) -> None:
    admin = login(client)

    batch = _create_codes(client, admin, amount_cents=50_000, quantity=3, expires_in_days=30)

    assert re.fullmatch(r"RDM-\d{8}-[A-Z0-9]{4}", batch["batch_no"])
    assert len(batch["items"]) == 3
    codes = {item["code"] for item in batch["items"]}
    assert len(codes) == 3
    assert all(re.fullmatch(r"RDM-[A-Z2-9]{4}-[A-Z2-9]{4}-[A-Z2-9]{4}", code) for code in codes)
    assert all(not (set("IO01") & set(code[4:].replace("-", ""))) for code in codes)
    for item in batch["items"]:
        assert set(item) == CODE_FIELDS
        assert item["amount_cents"] == 50_000
        assert item["status"] == "active"
        assert item["batch_no"] == batch["batch_no"]
        assert item["note"] == "测试批次"
        assert item["is_expired"] is False
        assert item["used_by"] is None
        assert item["used_at"] is None
        assert item["expires_at"] is not None
        assert item["created_at"]


def test_list_and_filter_redeem_codes(client: TestClient) -> None:
    admin = login(client)
    batch = _create_codes(client, admin, quantity=3)

    by_batch = _list_codes(client, admin, q=batch["batch_no"])
    assert by_batch["total"] == 3
    assert all(item["batch_no"] == batch["batch_no"] for item in by_batch["items"])

    assert _list_codes(client, admin, status="active")["total"] == 4
    assert _list_codes(client, admin, status="used")["total"] == 1
    assert _list_codes(client, admin, status="disabled")["total"] == 1

    page1 = _list_codes(client, admin, page=1, page_size=2)
    page2 = _list_codes(client, admin, page=2, page_size=2)
    assert page1["total"] == 6
    assert len(page1["items"]) == len(page2["items"]) == 2
    assert {item["id"] for item in page1["items"]}.isdisjoint(
        {item["id"] for item in page2["items"]}
    )


def test_disable_and_reenable_redeem_code(client: TestClient) -> None:
    admin = login(client)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    created = _create_codes(client, admin, amount_cents=25_000, quantity=1)["items"][0]

    disabled = client.patch(
        f"{ADMIN}/redeem-codes/{created['id']}",
        headers=_headers(admin),
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    # 同状态重复更新幂等。
    again = client.patch(
        f"{ADMIN}/redeem-codes/{created['id']}",
        headers=_headers(admin),
        json={"status": "disabled"},
    )
    assert again.status_code == 200

    blocked = client.post(
        f"{API_V1}/wallet/redeem", headers=_headers(viewer), json={"code": created["code"]}
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == "兑换码已停用"

    enabled = client.patch(
        f"{ADMIN}/redeem-codes/{created['id']}",
        headers=_headers(admin),
        json={"status": "active"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"

    redeemed = client.post(
        f"{API_V1}/wallet/redeem", headers=_headers(viewer), json={"code": created["code"]}
    )
    assert redeemed.status_code == 200, redeemed.text
    assert redeemed.json()["amount_cents"] == 25_000
    assert redeemed.json()["balance_cents"] == 175_000


def test_used_redeem_code_cannot_change_status(client: TestClient) -> None:
    admin = login(client)
    used = _list_codes(client, admin, q="RDM-DEMO-2026-0002")["items"][0]
    assert used["status"] == "used"
    assert used["used_by"]["display_name"] == "访客（演示）"

    response = client.patch(
        f"{ADMIN}/redeem-codes/{used['id']}",
        headers=_headers(admin),
        json={"status": "disabled"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "已使用的兑换码不能修改状态"


def test_expired_redeem_code_cannot_be_enabled(settings: Settings, client: TestClient) -> None:
    _setup_code(settings, code="RDM-TEST-EXPIRED", status="disabled", expired=True)
    admin = login(client)

    listed = _list_codes(client, admin, q="RDM-TEST-EXPIRED")
    assert listed["total"] == 1
    assert listed["items"][0]["is_expired"] is True

    response = client.patch(
        f"{ADMIN}/redeem-codes/{listed['items'][0]['id']}",
        headers=_headers(admin),
        json={"status": "active"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "已过期的兑换码不能启用"


def test_update_unknown_redeem_code_is_404(client: TestClient) -> None:
    admin = login(client)

    response = client.patch(
        f"{ADMIN}/redeem-codes/999999", headers=_headers(admin), json={"status": "disabled"}
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"amount_cents": 99, "quantity": 1},
        {"amount_cents": 100_000_001, "quantity": 1},
        {"amount_cents": 1000, "quantity": 0},
        {"amount_cents": 1000, "quantity": 101},
        {"amount_cents": 1000, "quantity": 1, "expires_in_days": 0},
        {"amount_cents": 1000, "quantity": 1, "expires_in_days": 3651},
        {"amount_cents": 1000, "quantity": 1, "note": "x" * 121},
    ],
)
def test_create_redeem_codes_validation(client: TestClient, payload: dict[str, object]) -> None:
    admin = login(client)

    response = client.post(f"{ADMIN}/redeem-codes", headers=_headers(admin), json=payload)

    assert response.status_code == 422


def test_redeem_code_query_validation(client: TestClient) -> None:
    admin = login(client)

    assert (
        client.get(
            f"{ADMIN}/redeem-codes", params={"status": "invalid"}, headers=_headers(admin)
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"{ADMIN}/redeem-codes/1", headers=_headers(admin), json={"status": "used"}
        ).status_code
        == 422
    )


# ---------- 系统设置 ----------


def test_get_settings_in_fixed_order(client: TestClient) -> None:
    admin = login(client)

    response = client.get(f"{ADMIN}/settings", headers=_headers(admin))

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["key"] for item in items] == [
        "platform_name",
        "support_contact",
        "wallet_recharge_note",
    ]
    assert all(set(item) == {"key", "value", "updated_at"} for item in items)
    values = {item["key"]: item["value"] for item in items}
    assert values == {
        "platform_name": "STELLERA HUB",
        "support_contact": "support@stellera.example",
        "wallet_recharge_note": "在线充值暂未开放，如需充值请联系平台客服。",
    }
    assert all(item["updated_at"] for item in items)


def test_update_settings_and_wallet_reflects_changes(client: TestClient) -> None:
    admin = login(client)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.patch(
        f"{ADMIN}/settings",
        headers=_headers(admin),
        json={
            "values": {
                "platform_name": "  STELLERA HUB 测试  ",
                "support_contact": "help@stellera.example",
                "wallet_recharge_note": "充值请联系平台客服（测试）。",
            }
        },
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["key"] for item in items] == [
        "platform_name",
        "support_contact",
        "wallet_recharge_note",
    ]
    assert items[0]["value"] == "STELLERA HUB 测试"
    assert items[1]["value"] == "help@stellera.example"

    summary = client.get(f"{API_V1}/wallet", headers=_headers(viewer)).json()
    assert summary["support_contact"] == "help@stellera.example"
    assert summary["recharge_note"] == "充值请联系平台客服（测试）。"
    assert summary["recharge_enabled"] is False


@pytest.mark.parametrize(
    "values",
    [
        {"unknown_key": "value"},
        {"platform_name": "   "},
        {"platform_name": "x" * 65},
        {"support_contact": "x" * 129},
        {"wallet_recharge_note": "x" * 301},
    ],
)
def test_update_settings_validation(client: TestClient, values: dict[str, str]) -> None:
    admin = login(client)

    response = client.patch(f"{ADMIN}/settings", headers=_headers(admin), json={"values": values})

    assert response.status_code == 422


def test_update_settings_requires_at_least_one_value(client: TestClient) -> None:
    admin = login(client)

    response = client.patch(f"{ADMIN}/settings", headers=_headers(admin), json={"values": {}})

    assert response.status_code == 422
