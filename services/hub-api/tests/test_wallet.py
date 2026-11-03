"""钱包模块端到端测试：汇总、流水、兑换码与 FDE 订单资金联动。

全部跑在临时 SQLite 上；种子数据在 TestClient 启动前写入（见 tests/conftest.py）。
演示余额：viewer 150,000 分、enterprise 212,300,000 分、engineer 15,700,000 分。
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import Settings
from app.db import create_engine, create_session_factory
from app.models.base import utcnow
from app.models.fde import FdeOrder
from app.models.redeem import RedeemCode
from app.models.user import User
from tests.conftest import (
    API_V1,
    ENGINEER_PASSWORD,
    ENGINEER_USERNAME,
    ENTERPRISE_PASSWORD,
    ENTERPRISE_USERNAME,
    VIEWER_PASSWORD,
    VIEWER_USERNAME,
    auth_headers,
    login,
)

WALLET = f"{API_V1}/wallet"
FDE = f"{API_V1}/fde"

SUMMARY_FIELDS = {
    "balance_cents",
    "usage_total_cents",
    "recharge_total_cents",
    "redeem_total_cents",
    "income_total_cents",
    "recharge_enabled",
    "recharge_note",
    "support_contact",
}

TRANSACTION_FIELDS = {
    "id",
    "type",
    "direction",
    "amount_cents",
    "balance_after_cents",
    "description",
    "reference_type",
    "reference_id",
    "created_at",
}

DEFAULT_RECHARGE_NOTE = "在线充值暂未开放，如需充值请联系平台客服。"
DEFAULT_SUPPORT_CONTACT = "support@stellera.example"


# ---------- 测试辅助 ----------


def _headers(pair: dict) -> dict[str, str]:
    return auth_headers(pair["access_token"])


def _summary(client: TestClient, pair: dict) -> dict:
    response = client.get(WALLET, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _transactions(client: TestClient, pair: dict, **params: str | int) -> dict:
    response = client.get(f"{WALLET}/transactions", params=params, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _publish(
    client: TestClient,
    pair: dict,
    *,
    price_cents: int = 1_000_000,
    title: str = "钱包联动测试订单",
) -> dict:
    response = client.post(
        f"{FDE}/orders",
        headers=_headers(pair),
        json={
            "title": title,
            "industry": "医疗健康",
            "description": "钱包联动测试",
            "delivery_days": 7,
            "price_cents": price_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _setup_legacy_order(
    settings: Settings,
    *,
    code: str,
    status: str,
) -> int:
    """直接写库造一条没有 order_payment 流水的历史订单。"""

    async def _run() -> int:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                publisher = (
                    await session.execute(select(User).where(User.username == ENTERPRISE_USERNAME))
                ).scalar_one()
                engineer = (
                    await session.execute(select(User).where(User.username == ENGINEER_USERNAME))
                ).scalar_one()
                now = utcnow()
                order = FdeOrder(
                    code=code,
                    title="历史订单（无托管流水）",
                    industry="医疗健康",
                    description="直接写库，未经过发布扣款流程",
                    delivery_days=5,
                    price_cents=1_000_000,
                    status=status,
                    escrow_status="held",
                    publisher_id=publisher.id,
                    engineer_id=engineer.id if status == "in_progress" else None,
                    claimed_at=now if status == "in_progress" else None,
                )
                session.add(order)
                await session.commit()
                return order.id
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def _setup_expired_code(settings: Settings, *, code: str = "RDM-TEST-EXPIRED") -> None:
    """直接写库造一个已过期的兑换码（接口不提供过期时间定制）。"""

    async def _run() -> None:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                session.add(
                    RedeemCode(
                        code=code,
                        amount_cents=10_000,
                        status="active",
                        batch_no="RDM-TEST",
                        note=None,
                        created_by_id=None,
                        used_by_id=None,
                        used_at=None,
                        expires_at=utcnow() - timedelta(days=1),
                        created_at=utcnow() - timedelta(days=10),
                    )
                )
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())


# ---------- 认证 ----------


def test_wallet_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(WALLET).status_code == 401
    assert client.get(f"{WALLET}/transactions").status_code == 401
    assert client.post(f"{WALLET}/redeem", json={"code": "RDM-DEMO-2026-0001"}).status_code == 401


# ---------- 汇总 ----------


def test_viewer_wallet_summary(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    body = _summary(client, viewer)

    assert set(body) == SUMMARY_FIELDS
    assert body["balance_cents"] == 150_000
    assert body["usage_total_cents"] == 0
    assert body["recharge_total_cents"] == 50_000
    assert body["redeem_total_cents"] == 100_000
    assert body["income_total_cents"] == 0
    # 在线充值永久关闭。
    assert body["recharge_enabled"] is False
    assert body["recharge_note"] == DEFAULT_RECHARGE_NOTE
    assert body["support_contact"] == DEFAULT_SUPPORT_CONTACT


def test_enterprise_wallet_summary(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    body = _summary(client, enterprise)

    assert body["balance_cents"] == 212_300_000
    assert body["usage_total_cents"] == 87_700_000
    assert body["recharge_total_cents"] == 300_000_000
    assert body["redeem_total_cents"] == 0
    assert body["income_total_cents"] == 0


def test_engineer_wallet_summary(client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)

    body = _summary(client, engineer)

    assert body["balance_cents"] == 15_700_000
    assert body["usage_total_cents"] == 0
    assert body["income_total_cents"] == 15_700_000


# ---------- 流水 ----------


def test_viewer_transactions_envelope_and_order(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    body = _transactions(client, viewer)

    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert set(body["items"][0]) == TRANSACTION_FIELDS
    # 最新在前：兑换（70 天前）晚于演示充值（120 天前）。
    assert [item["type"] for item in body["items"]] == ["redeem", "recharge"]
    assert body["items"][0]["direction"] == "credit"
    assert body["items"][0]["amount_cents"] == 100_000
    assert body["items"][0]["balance_after_cents"] == 150_000
    assert body["items"][1]["balance_after_cents"] == 50_000


def test_ledger_supports_type_filter_and_pagination(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    all_items = _transactions(client, enterprise, page_size=100)["items"]
    created_keys = [item["created_at"] for item in all_items]
    assert created_keys == sorted(created_keys, reverse=True)
    assert len(all_items) == 11

    payments = _transactions(client, enterprise, type="order_payment", page_size=100)
    assert payments["total"] == 10
    assert all(item["type"] == "order_payment" for item in payments["items"])
    assert all(item["direction"] == "debit" for item in payments["items"])

    refunds = _transactions(client, enterprise, type="order_refund")
    assert refunds["total"] == 0
    assert refunds["items"] == []

    page1 = _transactions(client, enterprise, page=1, page_size=4)
    page2 = _transactions(client, enterprise, page=2, page_size=4)
    page3 = _transactions(client, enterprise, page=3, page_size=4)
    assert page1["total"] == 11
    assert len(page1["items"]) == len(page2["items"]) == 4
    assert len(page3["items"]) == 3
    page1_ids = {item["id"] for item in page1["items"]}
    page2_ids = {item["id"] for item in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


def test_engineer_settlement_transactions(client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)

    body = _transactions(client, engineer, type="order_settlement")

    assert body["total"] == 2
    assert {item["amount_cents"] for item in body["items"]} == {11_200_000, 4_500_000}
    assert all(item["reference_type"] == "fde_order" for item in body["items"])


@pytest.mark.parametrize(
    "params",
    [
        {"type": "withdraw"},
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_transactions_reject_invalid_query_params(
    client: TestClient, params: dict[str, str | int]
) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.get(f"{WALLET}/transactions", params=params, headers=_headers(viewer))

    assert response.status_code == 422


# ---------- 兑换码 ----------


def test_redeem_code_credits_wallet(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.post(
        f"{WALLET}/redeem",
        json={"code": "  rdm-demo-2026-0001  "},
        headers=_headers(viewer),
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"amount_cents", "balance_cents", "transaction"}
    assert body["amount_cents"] == 100_000
    assert body["balance_cents"] == 250_000
    assert set(body["transaction"]) == TRANSACTION_FIELDS
    assert body["transaction"]["type"] == "redeem"
    assert body["transaction"]["direction"] == "credit"
    assert body["transaction"]["amount_cents"] == 100_000
    assert body["transaction"]["balance_after_cents"] == 250_000

    assert _summary(client, viewer)["balance_cents"] == 250_000
    assert _transactions(client, viewer)["total"] == 3

    # 兑换码变为已使用，且记录使用人。
    admin = login(client)
    codes = client.get(
        f"{API_V1}/admin/redeem-codes",
        params={"q": "RDM-DEMO-2026-0001"},
        headers=_headers(admin),
    ).json()
    assert codes["total"] == 1
    assert codes["items"][0]["status"] == "used"
    assert codes["items"][0]["used_by"] == {
        "id": viewer["user"]["id"],
        "display_name": "访客（演示）",
    }


def test_redeem_unknown_code_is_404(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.post(
        f"{WALLET}/redeem", json={"code": "RDM-NOPE-0000"}, headers=_headers(viewer)
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "兑换码不存在"


def test_redeem_disabled_code_conflicts(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.post(
        f"{WALLET}/redeem", json={"code": "RDM-DEMO-2026-0003"}, headers=_headers(viewer)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "兑换码已停用"


def test_redeem_expired_code_conflicts(settings: Settings, client: TestClient) -> None:
    _setup_expired_code(settings)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.post(
        f"{WALLET}/redeem", json={"code": "RDM-TEST-EXPIRED"}, headers=_headers(viewer)
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "兑换码已过期"
    assert _summary(client, viewer)["balance_cents"] == 150_000


def test_redeem_twice_conflicts(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    first = client.post(
        f"{WALLET}/redeem", json={"code": "RDM-DEMO-2026-0001"}, headers=_headers(viewer)
    )
    assert first.status_code == 200

    second = client.post(
        f"{WALLET}/redeem", json={"code": "RDM-DEMO-2026-0001"}, headers=_headers(viewer)
    )

    assert second.status_code == 409
    assert second.json()["detail"] == "兑换码已被使用"
    assert _summary(client, viewer)["balance_cents"] == 250_000


# ---------- FDE 订单资金联动 ----------


def test_publish_order_debits_escrow(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    order = _publish(client, enterprise, price_cents=1_000_000)

    summary = _summary(client, enterprise)
    assert summary["balance_cents"] == 211_300_000
    assert summary["usage_total_cents"] == 88_700_000

    latest = _transactions(client, enterprise)["items"][0]
    assert latest["type"] == "order_payment"
    assert latest["direction"] == "debit"
    assert latest["amount_cents"] == 1_000_000
    assert latest["balance_after_cents"] == 211_300_000
    assert latest["reference_type"] == "fde_order"
    assert latest["reference_id"] == order["id"]
    assert latest["description"] == f"发布订单 {order['code']} 托管"


def test_cancel_order_refunds_escrow(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    order = _publish(client, enterprise, price_cents=1_000_000)

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))

    assert response.status_code == 200
    assert response.json()["escrow_status"] == "refunded"
    assert _summary(client, enterprise)["balance_cents"] == 212_300_000
    latest = _transactions(client, enterprise)["items"][0]
    assert latest["type"] == "order_refund"
    assert latest["direction"] == "credit"
    assert latest["amount_cents"] == 1_000_000
    assert latest["reference_type"] == "fde_order"
    assert latest["reference_id"] == order["id"]
    assert latest["description"] == f"取消订单 {order['code']} 退款"


def test_complete_order_settles_engineer(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise, price_cents=2_000_000)
    claimed = client.post(f"{FDE}/orders/{order['id']}/claim", headers=_headers(engineer))
    assert claimed.status_code == 200

    completed = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))

    assert completed.status_code == 200
    assert completed.json()["escrow_status"] == "released"
    summary = _summary(client, engineer)
    assert summary["balance_cents"] == 17_700_000
    assert summary["income_total_cents"] == 17_700_000
    latest = _transactions(client, engineer)["items"][0]
    assert latest["type"] == "order_settlement"
    assert latest["direction"] == "credit"
    assert latest["amount_cents"] == 2_000_000
    assert latest["balance_after_cents"] == 17_700_000
    assert latest["reference_type"] == "fde_order"
    assert latest["reference_id"] == order["id"]
    assert latest["description"] == f"订单 {order['code']} 结算"


def test_publish_order_with_insufficient_balance_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    mine_before = client.get(f"{FDE}/orders/mine", headers=_headers(enterprise)).json()

    response = client.post(
        f"{FDE}/orders",
        headers=_headers(enterprise),
        json={
            "title": "余额不足的订单",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 3,
            "price_cents": 500_000_000,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "钱包余额不足，请先充值或兑换"
    # 失败时订单与扣款都不应落库。
    mine_after = client.get(f"{FDE}/orders/mine", headers=_headers(enterprise)).json()
    assert mine_after["total"] == mine_before["total"] == 10
    assert _summary(client, enterprise)["balance_cents"] == 212_300_000
    assert _transactions(client, enterprise)["total"] == 11


def test_cancel_legacy_order_without_escrow_does_not_refund(
    settings: Settings, client: TestClient
) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    order_id = _setup_legacy_order(settings, code="FDE-DEMO-9998", status="open")

    response = client.post(f"{FDE}/orders/{order_id}/cancel", headers=_headers(enterprise))

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    # 没有托管扣款流水，就不能凭空退款。
    assert _summary(client, enterprise)["balance_cents"] == 212_300_000
    assert _transactions(client, enterprise)["total"] == 11
    types = [item["type"] for item in _transactions(client, enterprise)["items"]]
    assert "order_refund" not in types


def test_complete_legacy_order_without_escrow_does_not_settle(
    settings: Settings, client: TestClient
) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order_id = _setup_legacy_order(settings, code="FDE-DEMO-9997", status="in_progress")

    response = client.post(f"{FDE}/orders/{order_id}/complete", headers=_headers(enterprise))

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    # 没有托管扣款流水，就不能凭空结算。
    assert _summary(client, engineer)["balance_cents"] == 15_700_000
    settlements = _transactions(client, engineer, type="order_settlement")
    assert settlements["total"] == 2
    assert all(item["reference_id"] != order_id for item in settlements["items"])
