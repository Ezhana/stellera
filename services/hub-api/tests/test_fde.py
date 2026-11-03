"""FDE 订单模块端到端测试：大厅、发布、申请审批流、工作日志、取消、实时推送。

全部跑在临时 SQLite 上，不依赖 Docker/PostgreSQL；种子数据在 TestClient
启动前写入（见 tests/conftest.py）。
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.core.config import Settings
from app.db import create_engine, create_session_factory
from app.models.fde import FdeOrder
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.security.passwords import hash_password
from tests.conftest import (
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

FDE = f"{API_V1}/fde"

ORDER_FIELDS = {
    "id",
    "code",
    "title",
    "industry",
    "description",
    "delivery_days",
    "price_cents",
    "status",
    "escrow_status",
    "publisher",
    "engineer",
    "work_log_count",
    "created_at",
    "updated_at",
    "claimed_at",
    "completed_at",
}

USER_REF_FIELDS = {"id", "display_name", "certification"}

APPLICATION_FIELDS = {
    "id",
    "order",
    "type",
    "status",
    "message",
    "review_note",
    "applicant",
    "reviewer",
    "reviewed_at",
    "created_at",
}


# ---------- 测试辅助 ----------


def _headers(pair: dict[str, Any]) -> dict[str, str]:
    return auth_headers(pair["access_token"])


def _publish(
    client: TestClient,
    pair: dict[str, Any],
    *,
    title: str = "测试需求：工业视觉缺陷检测",
    industry: str = "医疗健康",
    description: str = "测试描述",
    delivery_days: int = 10,
    price_cents: int = 10_000,
) -> dict[str, Any]:
    response = client.post(
        f"{FDE}/orders",
        headers=_headers(pair),
        json={
            "title": title,
            "industry": industry,
            "description": description,
            "delivery_days": delivery_days,
            "price_cents": price_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _apply(
    client: TestClient,
    pair: dict[str, Any],
    order_id: int,
    *,
    application_type: str = "accept",
    message: str | None = None,
) -> dict[str, Any]:
    response = client.post(
        f"{FDE}/orders/{order_id}/applications",
        headers=_headers(pair),
        json={"type": application_type, "message": message},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(
    client: TestClient,
    pair: dict[str, Any],
    application_id: int,
    *,
    note: str | None = "同意",
) -> dict[str, Any]:
    response = client.post(
        f"{FDE}/applications/{application_id}/approve",
        headers=_headers(pair),
        json={"note": note},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _add_log(
    client: TestClient,
    pair: dict[str, Any],
    order_id: int,
    *,
    content: str = "完成数据清洗与基线模型",
    worked_hours: float | None = 6.5,
) -> dict[str, Any]:
    response = client.post(
        f"{FDE}/orders/{order_id}/logs",
        headers=_headers(pair),
        json={"content": content, "worked_hours": worked_hours},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _find_by_code(client: TestClient, pair: dict[str, Any], code: str) -> dict[str, Any]:
    response = client.get(f"{FDE}/orders", params={"q": code}, headers=_headers(pair))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items, f"未找到订单 {code}"
    return items[0]


def _accept_order(
    client: TestClient,
    publisher: dict[str, Any],
    engineer: dict[str, Any],
    *,
    price_cents: int = 10_000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """发布 -> 申请接单 -> 发布者通过，返回 (order, application)。"""
    order = _publish(client, publisher, price_cents=price_cents)
    application = _apply(client, engineer, order["id"])
    approved = _approve(client, publisher, application["id"])
    return approved["order"], approved


def _create_user_with_role(
    settings: Settings,
    *,
    username: str,
    password: str,
    full_name: str,
    role_name: str,
) -> None:
    """直接写库创建测试用户（模拟“另一个工程师”等种子外账号）。"""

    async def _run() -> None:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                role = (
                    await session.execute(select(Role).where(Role.name == role_name))
                ).scalar_one()
                user = User(
                    username=username,
                    email=f"{username}@example.com",
                    hashed_password=hash_password(password),
                    full_name=full_name,
                    is_active=True,
                )
                session.add(user)
                await session.flush()
                session.add(UserRole(user_id=user.id, role_id=role.id))
                await session.commit()
        finally:
            await engine.dispose()

    asyncio.run(_run())


def _create_order_with_publisher(
    settings: Settings,
    *,
    publisher_username: str,
    code: str,
    status: str = "open",
    engineer_username: str | None = None,
) -> int:
    """直接写库创建订单，用于构造历史 / 越权场景。"""

    async def _run() -> int:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                publisher = (
                    await session.execute(select(User).where(User.username == publisher_username))
                ).scalar_one()
                engineer = (
                    (
                        await session.execute(
                            select(User).where(User.username == engineer_username)
                        )
                    ).scalar_one_or_none()
                    if engineer_username
                    else None
                )
                order = FdeOrder(
                    code=code,
                    title="直接写库的订单",
                    industry="医疗健康",
                    description="用于构造越权场景",
                    delivery_days=5,
                    price_cents=100_000,
                    status=status,
                    escrow_status="held",
                    publisher_id=publisher.id,
                    engineer_id=engineer.id if engineer else None,
                )
                session.add(order)
                await session.commit()
                return order.id
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# ---------- 认证与订单大厅 ----------


def test_http_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(f"{FDE}/orders").status_code == 401
    assert client.get(f"{FDE}/orders/1").status_code == 401
    assert client.get(f"{FDE}/orders/mine").status_code == 401
    assert client.get(f"{FDE}/orders/assigned").status_code == 401
    assert client.get(f"{FDE}/applications/mine").status_code == 401
    assert client.get(f"{FDE}/applications/received").status_code == 401
    assert client.post(f"{FDE}/orders", json={}).status_code == 401
    assert client.post(f"{FDE}/orders/1/applications", json={"type": "accept"}).status_code == 401
    assert client.post(f"{FDE}/orders/1/logs", json={"content": "x"}).status_code == 401
    assert client.post(f"{FDE}/orders/1/cancel").status_code == 401
    assert client.post(f"{FDE}/applications/1/approve", json={}).status_code == 401
    assert client.post(f"{FDE}/applications/1/reject", json={}).status_code == 401
    assert client.post(f"{FDE}/applications/1/withdraw").status_code == 401


def test_authenticated_user_can_list_order_hall(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{FDE}/orders", headers=_headers(member))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 10
    assert len(body["items"]) == 10
    assert body["page"] == 1
    assert body["page_size"] == 20
    first = body["items"][0]
    assert set(first) == ORDER_FIELDS
    assert set(first["publisher"]) == USER_REF_FIELDS
    assert first["publisher"]["display_name"] == "企业（演示）"
    assert first["publisher"]["certification"] == "enterprise"


def test_order_hall_is_ordered_newest_first(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    items = client.get(f"{FDE}/orders", params={"page_size": 100}, headers=_headers(member)).json()[
        "items"
    ]

    keys = [(_parse_time(item["created_at"]), item["id"]) for item in items]
    assert keys == sorted(keys, reverse=True)


# ---------- 发布需求 ----------


@pytest.mark.parametrize(
    ("username", "password", "certification"),
    [
        (MEMBER_USERNAME, MEMBER_PASSWORD, None),
        (ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD, "enterprise"),
        (ENGINEER_USERNAME, ENGINEER_PASSWORD, "engineer"),
    ],
)
def test_any_logged_in_role_can_publish_order(
    client: TestClient, username: str, password: str, certification: str | None
) -> None:
    pair = login(client, username, password)
    publisher_id = pair["user"]["id"]

    order = _publish(client, pair, title="激光雷达点云标注平台")

    assert re.fullmatch(r"FDE-\d{4}-\d{4}", order["code"])
    assert order["status"] == "open"
    assert order["escrow_status"] == "held"
    assert order["publisher"] == {
        "id": publisher_id,
        "display_name": pair["user"]["full_name"],
        "certification": certification,
    }
    assert order["engineer"] is None
    assert order["work_log_count"] == 0

    hall = client.get(f"{FDE}/orders", headers=_headers(pair)).json()
    assert any(item["id"] == order["id"] for item in hall["items"])

    mine = client.get(f"{FDE}/orders/mine", headers=_headers(pair)).json()
    assert any(item["id"] == order["id"] for item in mine["items"])
    assert all(item["publisher"]["id"] == publisher_id for item in mine["items"])

    detail = client.get(f"{FDE}/orders/{order['id']}", headers=_headers(pair)).json()
    assert detail["id"] == order["id"]
    assert detail["logs"] == []


def test_publish_payload_validation(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    response = client.post(
        f"{FDE}/orders",
        headers=_headers(enterprise),
        json={"title": "", "industry": "医疗健康", "delivery_days": 0, "price_cents": 0},
    )

    assert response.status_code == 422


# ---------- 申请接单 / 审批 ----------


def test_apply_accept_then_publisher_approves(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)

    application = _apply(client, engineer, order["id"], message="我有相关项目经验")

    assert set(application) == APPLICATION_FIELDS
    assert application["type"] == "accept"
    assert application["status"] == "pending"
    assert application["message"] == "我有相关项目经验"
    assert application["reviewer"] is None
    assert application["reviewed_at"] is None
    assert application["order"]["status"] == "open"
    assert application["applicant"] == {
        "id": engineer["user"]["id"],
        "display_name": "工程师（演示）",
        "certification": "engineer",
    }

    # 申请人自己的“我的申请”与发布者的“收到的申请”都能看到。
    mine = client.get(f"{FDE}/applications/mine", headers=_headers(engineer)).json()
    assert mine["total"] == 1
    received = client.get(f"{FDE}/applications/received", headers=_headers(enterprise)).json()
    assert received["total"] == 1
    assert received["items"][0]["id"] == application["id"]

    # 审批前订单仍然 open。
    detail = client.get(f"{FDE}/orders/{order['id']}", headers=_headers(enterprise)).json()
    assert detail["status"] == "open"
    assert detail["engineer"] is None

    approved = _approve(client, enterprise, application["id"])

    assert approved["status"] == "approved"
    assert approved["review_note"] == "同意"
    assert approved["reviewed_at"] is not None
    assert approved["reviewer"] == {
        "id": enterprise["user"]["id"],
        "display_name": "企业（演示）",
        "certification": "enterprise",
    }
    updated_order = approved["order"]
    assert updated_order["status"] == "in_progress"
    assert updated_order["engineer"] == {
        "id": engineer["user"]["id"],
        "display_name": "工程师（演示）",
        "certification": "engineer",
    }
    assert updated_order["claimed_at"] is not None
    assert updated_order["escrow_status"] == "held"

    # 审批后申请项里的订单也是最新状态。
    mine = client.get(f"{FDE}/applications/mine", headers=_headers(engineer)).json()
    assert mine["items"][0]["order"]["status"] == "in_progress"


def test_cannot_apply_for_own_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(
        f"{FDE}/orders/{order['id']}/applications",
        headers=_headers(enterprise),
        json={"type": "accept"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "不能申请自己发布的订单"


def test_duplicate_pending_accept_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _apply(client, engineer, order["id"])

    response = client.post(
        f"{FDE}/orders/{order['id']}/applications",
        headers=_headers(engineer),
        json={"type": "accept"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "已提交过申请，请等待审批"


def test_apply_accept_requires_open_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    response = client.post(
        f"{FDE}/orders/{in_progress['id']}/applications",
        headers=_headers(engineer),
        json={"type": "accept"},
    )

    assert response.status_code == 409
    assert "不在待接单状态" in response.json()["detail"]


def test_non_publisher_cannot_approve_or_reject(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])

    approve = client.post(
        f"{FDE}/applications/{application['id']}/approve",
        headers=_headers(member),
        json={"note": "越权"},
    )
    reject = client.post(
        f"{FDE}/applications/{application['id']}/reject",
        headers=_headers(member),
        json={"note": "越权"},
    )

    assert approve.status_code == 403
    assert reject.status_code == 403


def test_approve_rejects_other_pending_accepts(settings: Settings, client: TestClient) -> None:
    _create_user_with_role(
        settings,
        username="engineer2",
        password="engineer2-12345",
        full_name="工程师（二号）",
        role_name="engineer",
    )
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    engineer2 = login(client, "engineer2", "engineer2-12345")
    order = _publish(client, enterprise)
    first = _apply(client, engineer, order["id"], message="第一个申请")
    second = _apply(client, engineer2, order["id"], message="第二个申请")

    approved = _approve(client, enterprise, second["id"])

    assert approved["status"] == "approved"
    rejected = client.get(
        f"{FDE}/applications/mine", params={"status": "rejected"}, headers=_headers(engineer)
    ).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["id"] == first["id"]
    assert rejected["items"][0]["review_note"] == "订单已被其他申请人接单"
    assert rejected["items"][0]["reviewer"]["id"] == enterprise["user"]["id"]

    # 被驳回的申请不能再走审批。
    response = client.post(
        f"{FDE}/applications/{first['id']}/approve", headers=_headers(enterprise), json={}
    )
    assert response.status_code == 409


def test_approve_already_processed_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])
    _approve(client, enterprise, application["id"])

    response = client.post(
        f"{FDE}/applications/{application['id']}/approve", headers=_headers(enterprise), json={}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "申请已处理，无法重复审批"


def test_approve_unknown_application_is_404(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    response = client.post(
        f"{FDE}/applications/999999/approve", headers=_headers(enterprise), json={}
    )

    assert response.status_code == 404


def test_reject_application(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])

    response = client.post(
        f"{FDE}/applications/{application['id']}/reject",
        headers=_headers(enterprise),
        json={"note": "经验不匹配"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["review_note"] == "经验不匹配"
    assert body["reviewer"]["certification"] == "enterprise"
    assert body["order"]["status"] == "open"

    # 被驳回后可以重新申请。
    again = _apply(client, engineer, order["id"])
    assert again["status"] == "pending"


def test_withdraw_application(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])

    forbidden = client.post(
        f"{FDE}/applications/{application['id']}/withdraw", headers=_headers(member)
    )
    assert forbidden.status_code == 403

    response = client.post(
        f"{FDE}/applications/{application['id']}/withdraw", headers=_headers(engineer)
    )
    assert response.status_code == 200
    assert response.json()["status"] == "withdrawn"

    # 已撤回不能重复撤回，也不能再被审批。
    assert (
        client.post(
            f"{FDE}/applications/{application['id']}/withdraw", headers=_headers(engineer)
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"{FDE}/applications/{application['id']}/approve",
            headers=_headers(enterprise),
            json={},
        ).status_code
        == 409
    )


# ---------- 申请交付 / 完成结算 ----------


def test_delivery_flow_completes_order_and_settles_engineer(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer, price_cents=2_000_000)

    delivery = _apply(client, engineer, in_progress["id"], application_type="delivery")

    assert delivery["type"] == "delivery"
    assert delivery["status"] == "pending"
    assert delivery["order"]["status"] == "in_progress"

    # 只有接单工程师可以申请交付。
    forbidden = client.post(
        f"{FDE}/orders/{in_progress['id']}/applications",
        headers=_headers(member),
        json={"type": "delivery"},
    )
    assert forbidden.status_code == 403

    completed = _approve(client, enterprise, delivery["id"])

    assert completed["status"] == "approved"
    assert completed["order"]["status"] == "completed"
    assert completed["order"]["escrow_status"] == "released"
    assert completed["order"]["completed_at"] is not None

    wallet = client.get(f"{API_V1}/wallet", headers=_headers(engineer)).json()
    assert wallet["balance_cents"] == 17_700_000
    assert wallet["income_total_cents"] == 17_700_000


def test_delivery_application_requires_in_progress_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(
        f"{FDE}/orders/{order['id']}/applications",
        headers=_headers(engineer),
        json={"type": "delivery"},
    )

    assert response.status_code == 409
    assert "不在进行中" in response.json()["detail"]


def test_delivery_application_requires_assignee(settings: Settings, client: TestClient) -> None:
    _create_user_with_role(
        settings,
        username="engineer2",
        password="engineer2-12345",
        full_name="工程师（二号）",
        role_name="engineer",
    )
    engineer2 = login(client, "engineer2", "engineer2-12345")
    order_id = _create_order_with_publisher(
        settings,
        publisher_username=ENTERPRISE_USERNAME,
        code="FDE-LEGACY-0002",
        status="in_progress",
        engineer_username=ENGINEER_USERNAME,
    )

    response = client.post(
        f"{FDE}/orders/{order_id}/applications",
        headers=_headers(engineer2),
        json={"type": "delivery"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "只有接单工程师可以申请交付"


def test_duplicate_pending_delivery_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)
    _apply(client, engineer, in_progress["id"], application_type="delivery")

    response = client.post(
        f"{FDE}/orders/{in_progress['id']}/applications",
        headers=_headers(engineer),
        json={"type": "delivery"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "已提交过交付申请，请等待审批"


# ---------- 工作日志 ----------


def test_assignee_submits_work_log_and_count_is_reflected(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    log = _add_log(client, engineer, in_progress["id"], content="完成数据清洗与基线模型")

    assert log["order_id"] == in_progress["id"]
    assert log["author"] == {
        "id": engineer["user"]["id"],
        "display_name": "工程师（演示）",
        "certification": "engineer",
    }
    assert log["content"] == "完成数据清洗与基线模型"
    assert log["worked_hours"] == 6.5
    assert log["created_at"]

    detail = client.get(f"{FDE}/orders/{in_progress['id']}", headers=_headers(enterprise)).json()
    assert detail["work_log_count"] == 1
    assert [item["id"] for item in detail["logs"]] == [log["id"]]
    assert detail["logs"][0]["author"]["certification"] == "engineer"

    hall_item = _find_by_code(client, enterprise, in_progress["code"])
    assert hall_item["work_log_count"] == 1


def test_worked_hours_is_optional(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    log = _add_log(client, engineer, in_progress["id"], worked_hours=None)

    assert log["worked_hours"] is None


def test_only_assignee_or_admin_can_submit_work_log(settings: Settings, client: TestClient) -> None:
    _create_user_with_role(
        settings,
        username="engineer2",
        password="engineer2-12345",
        full_name="工程师（二号）",
        role_name="engineer",
    )
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    other = login(client, "engineer2", "engineer2-12345")
    admin = login(client)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    other_attempt = client.post(
        f"{FDE}/orders/{in_progress['id']}/logs",
        headers=_headers(other),
        json={"content": "别人的订单", "worked_hours": 1.0},
    )
    assert other_attempt.status_code == 403

    publisher_attempt = client.post(
        f"{FDE}/orders/{in_progress['id']}/logs",
        headers=_headers(enterprise),
        json={"content": "发布者代填", "worked_hours": 1.0},
    )
    assert publisher_attempt.status_code == 403

    admin_log = _add_log(client, admin, in_progress["id"], content="管理员补录")
    assert admin_log["author"]["certification"] is None


def test_work_log_requires_in_progress_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(
        f"{FDE}/orders/{order['id']}/logs",
        headers=_headers(engineer),
        json={"content": "还没接单就写日志", "worked_hours": 1.0},
    )

    assert response.status_code == 409


# ---------- 取消 ----------


def test_publisher_cancels_open_order_refunds_and_rejects_pending(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise, price_cents=100_000)
    application = _apply(client, engineer, order["id"])

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["escrow_status"] == "refunded"
    assert body["completed_at"] is None

    # 取消时自动驳回该订单的 pending 接单申请。
    rejected = client.get(
        f"{FDE}/applications/mine", params={"status": "rejected"}, headers=_headers(engineer)
    ).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["id"] == application["id"]
    assert rejected["items"][0]["review_note"] == "订单已取消"

    # 取消后订单不能再次取消。
    again = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))
    assert again.status_code == 409

    wallet = client.get(f"{API_V1}/wallet", headers=_headers(enterprise)).json()
    assert wallet["balance_cents"] == 212_300_000


def test_cancel_in_progress_order_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    response = client.post(f"{FDE}/orders/{in_progress['id']}/cancel", headers=_headers(enterprise))

    assert response.status_code == 409


def test_non_publisher_cannot_cancel_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(member))

    assert response.status_code == 403


def test_legacy_claim_and_complete_endpoints_are_removed(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    # 旧端点已删除且不再有任何 RBAC 策略：中间件直接 403。
    assert client.post(f"{FDE}/orders/1/claim", headers=_headers(member)).status_code == 403
    assert client.post(f"{FDE}/orders/1/complete", headers=_headers(member)).status_code == 403


# ---------- 我发布的 / 我接到的 / 详情 ----------


def test_mine_only_returns_own_orders(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    admin = login(client)

    enterprise_mine = client.get(f"{FDE}/orders/mine", headers=_headers(enterprise)).json()
    assert enterprise_mine["total"] == 10
    assert all(
        item["publisher"]["id"] == enterprise["user"]["id"] for item in enterprise_mine["items"]
    )

    admin_mine = client.get(f"{FDE}/orders/mine", headers=_headers(admin)).json()
    assert admin_mine == {"items": [], "total": 0, "page": 1, "page_size": 20}

    admin_order = _publish(client, admin, title="管理员发布的订单")
    admin_mine = client.get(f"{FDE}/orders/mine", headers=_headers(admin)).json()
    assert admin_mine["total"] == 1
    assert admin_mine["items"][0]["id"] == admin_order["id"]

    # “我发布的”支持按状态过滤，且不影响别人的列表。
    open_mine = client.get(
        f"{FDE}/orders/mine", params={"status": "open"}, headers=_headers(enterprise)
    ).json()
    assert open_mine["total"] == 5
    assert all(item["status"] == "open" for item in open_mine["items"])


def test_assigned_only_returns_own_orders(client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    assigned = client.get(f"{FDE}/orders/assigned", headers=_headers(engineer)).json()

    assert set(assigned) == {"items", "total", "page", "page_size"}
    # 演示数据：3 条 in_progress + 2 条 completed 都是该工程师接单。
    assert assigned["total"] == 5
    assert all(item["engineer"]["id"] == engineer["user"]["id"] for item in assigned["items"])

    in_progress = client.get(
        f"{FDE}/orders/assigned", params={"status": "in_progress"}, headers=_headers(engineer)
    ).json()
    assert in_progress["total"] == 3
    assert all(item["status"] == "in_progress" for item in in_progress["items"])

    assert client.get(f"{FDE}/orders/assigned", headers=_headers(member)).json()["total"] == 0


def test_assigned_list_reflects_new_accepted_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    in_progress, _ = _accept_order(client, enterprise, engineer)

    assigned = client.get(f"{FDE}/orders/assigned", headers=_headers(engineer)).json()

    assert assigned["total"] == 6
    assert any(item["id"] == in_progress["id"] for item in assigned["items"])


def test_assigned_list_pagination_and_validation(client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)

    page1 = client.get(
        f"{FDE}/orders/assigned", params={"page": 1, "page_size": 2}, headers=_headers(engineer)
    ).json()
    page2 = client.get(
        f"{FDE}/orders/assigned", params={"page": 2, "page_size": 2}, headers=_headers(engineer)
    ).json()
    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert {item["id"] for item in page1["items"]}.isdisjoint(
        {item["id"] for item in page2["items"]}
    )

    for params in ({"status": "unknown"}, {"page": 0}, {"page_size": 101}):
        response = client.get(f"{FDE}/orders/assigned", params=params, headers=_headers(engineer))
        assert response.status_code == 422


def test_detail_returns_logs_oldest_first(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    demo = _find_by_code(client, member, "FDE-DEMO-0007")

    detail = client.get(f"{FDE}/orders/{demo['id']}", headers=_headers(member)).json()

    assert detail["work_log_count"] == 3
    assert len(detail["logs"]) == 3
    times = [_parse_time(log["created_at"]) for log in detail["logs"]]
    assert times == sorted(times)
    assert all(log["order_id"] == demo["id"] for log in detail["logs"])
    assert all(log["author"]["display_name"] == "工程师（演示）" for log in detail["logs"])
    assert all(log["author"]["certification"] == "engineer" for log in detail["logs"])


def test_detail_unknown_order_is_404(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{FDE}/orders/999999", headers=_headers(member))

    assert response.status_code == 404


# ---------- 申请列表 ----------


def test_application_lists_filters_and_pagination(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    order = _publish(client, enterprise)
    accept = _apply(client, engineer, order["id"])
    accepted_order, approved = _accept_order(client, enterprise, member)
    # 第一条申请被驳回，用于验证 received 列表的状态过滤。
    client.post(
        f"{FDE}/applications/{accept['id']}/reject",
        headers=_headers(enterprise),
        json={"note": "经验不匹配"},
    )

    # 我的申请：按状态 / 类型过滤。
    mine = client.get(f"{FDE}/applications/mine", headers=_headers(engineer)).json()
    assert set(mine) == {"items", "total", "page", "page_size"}
    assert mine["total"] == 1
    assert mine["items"][0]["id"] == accept["id"]

    member_mine = client.get(
        f"{FDE}/applications/mine", params={"status": "approved"}, headers=_headers(member)
    ).json()
    assert member_mine["total"] == 1
    assert member_mine["items"][0]["type"] == "accept"

    empty = client.get(
        f"{FDE}/applications/mine", params={"type": "delivery"}, headers=_headers(engineer)
    ).json()
    assert empty["total"] == 0

    # 收到的申请：只有订单发布者能看到。
    received = client.get(f"{FDE}/applications/received", headers=_headers(enterprise)).json()
    assert received["total"] == 2
    assert {item["order"]["publisher"]["id"] for item in received["items"]} == {
        enterprise["user"]["id"]
    }
    # member 自己发布的订单收到的申请（enterprise 申请接单）。
    member_order = _publish(client, member, title="member 发布的需求")
    _apply(client, enterprise, member_order["id"])
    member_received = client.get(f"{FDE}/applications/received", headers=_headers(member)).json()
    assert member_received["total"] == 1
    assert member_received["items"][0]["order"]["publisher"]["id"] == member["user"]["id"]

    rejected = client.get(
        f"{FDE}/applications/received", params={"status": "rejected"}, headers=_headers(enterprise)
    ).json()
    assert rejected["total"] == 1
    assert rejected["items"][0]["id"] == accept["id"]
    assert rejected["items"][0]["review_note"] == "经验不匹配"

    page1 = client.get(
        f"{FDE}/applications/received",
        params={"page": 1, "page_size": 1},
        headers=_headers(enterprise),
    ).json()
    page2 = client.get(
        f"{FDE}/applications/received",
        params={"page": 2, "page_size": 1},
        headers=_headers(enterprise),
    ).json()
    assert page1["total"] == 2
    assert {item["id"] for item in page1["items"]}.isdisjoint(
        {item["id"] for item in page2["items"]}
    )
    # 已接单订单的申请项里订单应为最新状态。
    assert {item["order"]["status"] for item in received["items"]} <= {"open", "in_progress"}
    assert accepted_order["id"] in {item["order"]["id"] for item in received["items"]}


@pytest.mark.parametrize(
    "params",
    [
        {"type": "unknown"},
        {"status": "unknown"},
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_application_list_query_validation(
    client: TestClient, params: dict[str, str | int]
) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{FDE}/applications/mine", params=params, headers=_headers(member))

    assert response.status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "unknown"},
        {"message": "x" * 501},
    ],
)
def test_application_payload_validation(client: TestClient, payload: dict[str, str]) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    body = {"type": "accept", **payload}

    response = client.post(
        f"{FDE}/orders/{order['id']}/applications",
        headers=_headers(engineer),
        json=body,
    )

    assert response.status_code == 422


def test_review_note_length_validation(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])

    response = client.post(
        f"{FDE}/applications/{application['id']}/approve",
        headers=_headers(enterprise),
        json={"note": "x" * 501},
    )

    assert response.status_code == 422


def test_review_body_can_be_empty(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    application = _apply(client, engineer, order["id"])

    response = client.post(
        f"{FDE}/applications/{application['id']}/approve",
        headers=_headers(enterprise),
    )

    assert response.status_code == 200
    assert response.json()["review_note"] is None


# ---------- 过滤与分页 ----------


def test_list_filters(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    open_orders = client.get(
        f"{FDE}/orders", params={"status": "open"}, headers=_headers(member)
    ).json()
    assert open_orders["total"] == 5
    assert all(item["status"] == "open" for item in open_orders["items"])

    medical = client.get(
        f"{FDE}/orders", params={"industry": "医疗健康"}, headers=_headers(member)
    ).json()
    assert medical["total"] == 2
    assert all(item["industry"] == "医疗健康" for item in medical["items"])

    # 关键字大小写不敏感：小写单号也能命中大写 code。
    by_code = client.get(
        f"{FDE}/orders", params={"q": "fde-demo-0001"}, headers=_headers(member)
    ).json()
    assert by_code["total"] == 1
    assert by_code["items"][0]["code"] == "FDE-DEMO-0001"

    by_title = client.get(f"{FDE}/orders", params={"q": "预测"}, headers=_headers(member)).json()
    assert by_title["total"] == 2

    combined = client.get(
        f"{FDE}/orders",
        params={"status": "in_progress", "industry": "医疗健康"},
        headers=_headers(member),
    ).json()
    assert combined["total"] == 1
    assert combined["items"][0]["code"] == "FDE-DEMO-0008"


def test_list_pagination_envelope(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    page1 = client.get(
        f"{FDE}/orders", params={"page": 1, "page_size": 3}, headers=_headers(member)
    ).json()
    page2 = client.get(
        f"{FDE}/orders", params={"page": 2, "page_size": 3}, headers=_headers(member)
    ).json()
    last_page = client.get(
        f"{FDE}/orders", params={"page": 4, "page_size": 3}, headers=_headers(member)
    ).json()

    assert page1["total"] == 10
    assert page1["page"] == 1
    assert page1["page_size"] == 3
    assert len(page1["items"]) == 3
    assert len(page2["items"]) == 3
    assert len(last_page["items"]) == 1
    page1_ids = {item["id"] for item in page1["items"]}
    page2_ids = {item["id"] for item in page2["items"]}
    assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.parametrize(
    "params",
    [
        {"status": "unknown"},
        {"page": 0},
        {"page_size": 0},
        {"page_size": 101},
    ],
)
def test_list_rejects_invalid_query_params(client: TestClient, params: dict[str, Any]) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{FDE}/orders", params=params, headers=_headers(member))

    assert response.status_code == 422


# ---------- 管理员 ----------


def test_admin_can_perform_all_order_actions(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    admin = login(client)

    # 管理员自己发布的订单同样不能申请接单（发布者不能申请自己的订单）。
    own = _publish(client, admin, title="管理员自己发布的需求")
    assert (
        client.post(
            f"{FDE}/orders/{own['id']}/applications",
            headers=_headers(admin),
            json={"type": "accept"},
        ).status_code
        == 409
    )

    # 管理员可以申请别人的订单，也可以审批别人的订单。
    order = _publish(client, enterprise)
    application = _apply(client, admin, order["id"])
    approved = _approve(client, enterprise, application["id"])
    assert approved["order"]["engineer"]["id"] == admin["user"]["id"]
    assert approved["order"]["engineer"]["certification"] is None

    log = _add_log(client, admin, order["id"], content="管理员补录的工作日志")
    assert log["author"]["id"] == admin["user"]["id"]

    delivery = _apply(client, admin, order["id"], application_type="delivery")
    completed = _approve(client, enterprise, delivery["id"])
    assert completed["order"]["status"] == "completed"

    # 管理员也可以取消别人发布的待接单订单。
    cancellable = _publish(client, enterprise, title="待取消订单")
    cancelled = client.post(f"{FDE}/orders/{cancellable['id']}/cancel", headers=_headers(admin))
    assert cancelled.status_code == 200
    assert cancelled.json()["escrow_status"] == "refunded"


# ---------- WebSocket 实时推送 ----------


def test_ws_rejects_missing_or_invalid_token(client: TestClient) -> None:
    # 服务端先 accept 再 close(4401)，浏览器侧才能观察到自定义关闭码。
    with client.websocket_connect(f"{FDE}/ws") as websocket:
        with pytest.raises(WebSocketDisconnect) as missing:
            websocket.receive_json()
    assert missing.value.code == 4401

    with client.websocket_connect(f"{FDE}/ws?token=not-a-jwt") as websocket:
        with pytest.raises(WebSocketDisconnect) as invalid:
            websocket.receive_json()
    assert invalid.value.code == 4401


def test_ws_sends_connected_frame(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    with client.websocket_connect(f"{FDE}/ws?token={member['access_token']}") as websocket:
        frame = websocket.receive_json()

    assert frame["type"] == "connected"
    assert _parse_time(frame["server_time"])


def test_ws_broadcasts_order_created_and_updated(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    with client.websocket_connect(f"{FDE}/ws?token={member['access_token']}") as websocket:
        assert websocket.receive_json()["type"] == "connected"

        order = _publish(client, enterprise, title="WebSocket 推送验证")
        created = websocket.receive_json()
        assert created["type"] == "order.created"
        assert set(created["order"]) == ORDER_FIELDS
        assert created["order"]["id"] == order["id"]
        assert created["order"]["status"] == "open"
        assert created["order"]["publisher"]["certification"] == "enterprise"

        # 创建申请不广播；审批通过才推送 order.updated。
        application = _apply(client, engineer, order["id"])
        _approve(client, enterprise, application["id"])
        in_progress = websocket.receive_json()
        assert in_progress["type"] == "order.updated"
        assert in_progress["order"]["status"] == "in_progress"
        assert in_progress["order"]["engineer"]["id"] == engineer["user"]["id"]

        _add_log(client, engineer, order["id"])
        logged = websocket.receive_json()
        assert logged["type"] == "order.updated"
        assert logged["order"]["work_log_count"] == 1

        delivery = _apply(client, engineer, order["id"], application_type="delivery")
        _approve(client, enterprise, delivery["id"])
        completed = websocket.receive_json()
        assert completed["type"] == "order.updated"
        assert completed["order"]["status"] == "completed"
        assert completed["order"]["escrow_status"] == "released"


def test_ws_does_not_broadcast_application_create_reject_or_withdraw(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    with client.websocket_connect(f"{FDE}/ws?token={member['access_token']}") as websocket:
        assert websocket.receive_json()["type"] == "connected"

        # 申请创建 / 驳回 / 撤回都不广播；用取消订单的广播作为“下一个事件”验证。
        rejected_order = _publish(client, enterprise, title="驳回场景")
        assert websocket.receive_json()["type"] == "order.created"
        rejected_application = _apply(client, engineer, rejected_order["id"])
        client.post(
            f"{FDE}/applications/{rejected_application['id']}/reject",
            headers=_headers(enterprise),
            json={"note": "驳回"},
        )
        client.post(f"{FDE}/orders/{rejected_order['id']}/cancel", headers=_headers(enterprise))
        rejected_cancel = websocket.receive_json()
        assert rejected_cancel["type"] == "order.updated"
        assert rejected_cancel["order"]["status"] == "cancelled"

        withdrawn_order = _publish(client, enterprise, title="撤回场景")
        assert websocket.receive_json()["type"] == "order.created"
        withdrawn_application = _apply(client, engineer, withdrawn_order["id"])
        client.post(
            f"{FDE}/applications/{withdrawn_application['id']}/withdraw",
            headers=_headers(engineer),
        )
        client.post(f"{FDE}/orders/{withdrawn_order['id']}/cancel", headers=_headers(enterprise))
        withdrawn_cancel = websocket.receive_json()
        assert withdrawn_cancel["type"] == "order.updated"
        assert withdrawn_cancel["order"]["status"] == "cancelled"
