"""FDE 订单模块端到端测试：订单大厅、我发布的、发布/认领/日志/完成/取消与实时推送。

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
    VIEWER_PASSWORD,
    VIEWER_USERNAME,
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
    price_cents: int = 1_000_000,
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


def _claim(client: TestClient, pair: dict[str, Any], order_id: int) -> dict[str, Any]:
    response = client.post(f"{FDE}/orders/{order_id}/claim", headers=_headers(pair))
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
) -> int:
    """直接写库创建一条 open 订单，用于验证“不能认领自己发布的订单”。"""

    async def _run() -> int:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                publisher = (
                    await session.execute(select(User).where(User.username == publisher_username))
                ).scalar_one()
                order = FdeOrder(
                    code=code,
                    title="工程师自己发布的订单",
                    industry="医疗健康",
                    description="用于验证发布者不能认领自己的订单",
                    delivery_days=5,
                    price_cents=100_000,
                    status="open",
                    escrow_status="held",
                    publisher_id=publisher.id,
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
    assert client.post(f"{FDE}/orders", json={}).status_code == 401
    assert client.post(f"{FDE}/orders/1/claim").status_code == 401


def test_authenticated_user_can_list_order_hall(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.get(f"{FDE}/orders", headers=_headers(viewer))

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 10
    assert len(body["items"]) == 10
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert set(body["items"][0]) == ORDER_FIELDS
    assert body["items"][0]["publisher"]["display_name"] == "企业（演示）"


def test_order_hall_is_ordered_newest_first(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    items = client.get(f"{FDE}/orders", params={"page_size": 100}, headers=_headers(viewer)).json()[
        "items"
    ]

    keys = [(_parse_time(item["created_at"]), item["id"]) for item in items]
    assert keys == sorted(keys, reverse=True)


# ---------- 发布需求 ----------


def test_enterprise_publishes_order_and_it_appears_in_hall_and_mine(
    client: TestClient,
) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    publisher_id = enterprise["user"]["id"]

    order = _publish(client, enterprise, title="激光雷达点云标注平台")

    assert re.fullmatch(r"FDE-\d{4}-\d{4}", order["code"])
    assert order["title"] == "激光雷达点云标注平台"
    assert order["status"] == "open"
    assert order["escrow_status"] == "held"
    assert order["publisher"] == {"id": publisher_id, "display_name": "企业（演示）"}
    assert order["engineer"] is None
    assert order["work_log_count"] == 0
    assert order["claimed_at"] is None
    assert order["completed_at"] is None

    hall = client.get(f"{FDE}/orders", headers=_headers(enterprise)).json()
    assert any(item["id"] == order["id"] for item in hall["items"])

    mine = client.get(f"{FDE}/orders/mine", headers=_headers(enterprise)).json()
    assert any(item["id"] == order["id"] for item in mine["items"])
    assert all(item["publisher"]["id"] == publisher_id for item in mine["items"])

    detail = client.get(f"{FDE}/orders/{order['id']}", headers=_headers(enterprise)).json()
    assert detail["id"] == order["id"]
    assert detail["logs"] == []


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (VIEWER_USERNAME, VIEWER_PASSWORD),
        (ENGINEER_USERNAME, ENGINEER_PASSWORD),
    ],
)
def test_users_without_enterprise_role_cannot_publish(
    client: TestClient, username: str, password: str
) -> None:
    pair = login(client, username, password)

    response = client.post(
        f"{FDE}/orders",
        headers=_headers(pair),
        json={
            "title": "越权发布",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 1,
            "price_cents": 1,
        },
    )

    assert response.status_code == 403


def test_publish_payload_validation(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    response = client.post(
        f"{FDE}/orders",
        headers=_headers(enterprise),
        json={"title": "", "industry": "医疗健康", "delivery_days": 0, "price_cents": 0},
    )

    assert response.status_code == 422


# ---------- 认领 ----------


def test_engineer_claims_open_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)

    claimed = _claim(client, engineer, order["id"])

    assert claimed["status"] == "in_progress"
    assert claimed["engineer"] == {
        "id": engineer["user"]["id"],
        "display_name": "工程师（演示）",
    }
    assert claimed["claimed_at"] is not None
    assert claimed["escrow_status"] == "held"

    # 已被认领的订单不能再次认领（即使发布者也不允许重复流转）。
    again = client.post(f"{FDE}/orders/{order['id']}/claim", headers=_headers(engineer))
    assert again.status_code == 409


def test_engineer_cannot_claim_own_order(settings: Settings, client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order_id = _create_order_with_publisher(
        settings, publisher_username=ENGINEER_USERNAME, code="FDE-DEMO-9999"
    )

    response = client.post(f"{FDE}/orders/{order_id}/claim", headers=_headers(engineer))

    assert response.status_code == 409


def test_viewer_cannot_claim_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(f"{FDE}/orders/{order['id']}/claim", headers=_headers(viewer))

    assert response.status_code == 403


# ---------- 工作日志 ----------


def test_assignee_submits_work_log_and_count_is_reflected(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    log = _add_log(client, engineer, order["id"], content="完成数据清洗与基线模型")

    assert log["order_id"] == order["id"]
    assert log["author"] == {"id": engineer["user"]["id"], "display_name": "工程师（演示）"}
    assert log["content"] == "完成数据清洗与基线模型"
    assert log["worked_hours"] == 6.5
    assert log["created_at"]

    detail = client.get(f"{FDE}/orders/{order['id']}", headers=_headers(enterprise)).json()
    assert detail["work_log_count"] == 1
    assert [item["id"] for item in detail["logs"]] == [log["id"]]

    hall_item = _find_by_code(client, enterprise, order["code"])
    assert hall_item["work_log_count"] == 1


def test_worked_hours_is_optional(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    log = _add_log(client, engineer, order["id"], worked_hours=None)

    assert log["worked_hours"] is None


def test_only_assignee_can_submit_work_log(settings: Settings, client: TestClient) -> None:
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
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    response = client.post(
        f"{FDE}/orders/{order['id']}/logs",
        headers=_headers(other),
        json={"content": "别人的订单", "worked_hours": 1.0},
    )

    assert response.status_code == 403
    # 发布者虽然拥有 complete/cancel 权限，也没有提交日志的权限。
    publisher_attempt = client.post(
        f"{FDE}/orders/{order['id']}/logs",
        headers=_headers(enterprise),
        json={"content": "发布者代填", "worked_hours": 1.0},
    )
    assert publisher_attempt.status_code == 403


def test_work_log_requires_in_progress_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(
        f"{FDE}/orders/{order['id']}/logs",
        headers=_headers(engineer),
        json={"content": "还没认领就写日志", "worked_hours": 1.0},
    )

    assert response.status_code == 409


# ---------- 完成 ----------


def test_publisher_completes_in_progress_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    response = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["escrow_status"] == "released"
    assert body["completed_at"] is not None

    # 已完成订单不能重复完成。
    again = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))
    assert again.status_code == 409


def test_complete_requires_in_progress_status(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))

    assert response.status_code == 409


def test_non_publisher_cannot_complete_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    response = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(engineer))

    assert response.status_code == 403


# ---------- 取消 ----------


def test_publisher_cancels_open_order_and_refunds_escrow(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "cancelled"
    assert body["escrow_status"] == "refunded"
    assert body["completed_at"] is None

    again = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))
    assert again.status_code == 409


def test_cancel_in_progress_order_conflicts(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    order = _publish(client, enterprise)
    _claim(client, engineer, order["id"])

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(enterprise))

    assert response.status_code == 409


def test_viewer_cannot_cancel_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    order = _publish(client, enterprise)

    response = client.post(f"{FDE}/orders/{order['id']}/cancel", headers=_headers(viewer))

    assert response.status_code == 403


# ---------- 我发布的 / 详情 ----------


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


def test_detail_returns_logs_oldest_first(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)
    demo = _find_by_code(client, viewer, "FDE-DEMO-0007")

    detail = client.get(f"{FDE}/orders/{demo['id']}", headers=_headers(viewer)).json()

    assert detail["work_log_count"] == 3
    assert len(detail["logs"]) == 3
    times = [_parse_time(log["created_at"]) for log in detail["logs"]]
    assert times == sorted(times)
    assert all(log["order_id"] == demo["id"] for log in detail["logs"])
    assert all(log["author"]["display_name"] == "工程师（演示）" for log in detail["logs"])


def test_detail_unknown_order_is_404(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.get(f"{FDE}/orders/999999", headers=_headers(viewer))

    assert response.status_code == 404


# ---------- 过滤与分页 ----------


def test_list_filters(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    open_orders = client.get(
        f"{FDE}/orders", params={"status": "open"}, headers=_headers(viewer)
    ).json()
    assert open_orders["total"] == 5
    assert all(item["status"] == "open" for item in open_orders["items"])

    medical = client.get(
        f"{FDE}/orders", params={"industry": "医疗健康"}, headers=_headers(viewer)
    ).json()
    assert medical["total"] == 2
    assert all(item["industry"] == "医疗健康" for item in medical["items"])

    # 关键字大小写不敏感：小写单号也能命中大写 code。
    by_code = client.get(
        f"{FDE}/orders", params={"q": "fde-demo-0001"}, headers=_headers(viewer)
    ).json()
    assert by_code["total"] == 1
    assert by_code["items"][0]["code"] == "FDE-DEMO-0001"

    by_title = client.get(f"{FDE}/orders", params={"q": "预测"}, headers=_headers(viewer)).json()
    assert by_title["total"] == 2

    combined = client.get(
        f"{FDE}/orders",
        params={"status": "in_progress", "industry": "医疗健康"},
        headers=_headers(viewer),
    ).json()
    assert combined["total"] == 1
    assert combined["items"][0]["code"] == "FDE-DEMO-0008"


def test_list_pagination_envelope(client: TestClient) -> None:
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    page1 = client.get(
        f"{FDE}/orders", params={"page": 1, "page_size": 3}, headers=_headers(viewer)
    ).json()
    page2 = client.get(
        f"{FDE}/orders", params={"page": 2, "page_size": 3}, headers=_headers(viewer)
    ).json()
    last_page = client.get(
        f"{FDE}/orders", params={"page": 4, "page_size": 3}, headers=_headers(viewer)
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
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    response = client.get(f"{FDE}/orders", params=params, headers=_headers(viewer))

    assert response.status_code == 422


# ---------- 管理员 ----------


def test_admin_can_perform_all_order_actions(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    admin = login(client)

    # 管理员自己发布的订单同样不能认领（发布者不能认领自己的订单）。
    own = _publish(client, admin, title="管理员自己发布的需求")
    assert (
        client.post(f"{FDE}/orders/{own['id']}/claim", headers=_headers(admin)).status_code == 409
    )

    # 管理员可以认领/写日志/完成别人的订单。
    order = _publish(client, enterprise)
    claimed = _claim(client, admin, order["id"])
    assert claimed["engineer"] == {"id": admin["user"]["id"], "display_name": "系统管理员"}
    log = _add_log(client, admin, order["id"], content="管理员补录的工作日志")
    assert log["author"]["id"] == admin["user"]["id"]
    completed = client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    # 管理员也可以取消别人发布的待认领订单。
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
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    with client.websocket_connect(f"{FDE}/ws?token={viewer['access_token']}") as websocket:
        frame = websocket.receive_json()

    assert frame["type"] == "connected"
    assert _parse_time(frame["server_time"])


def test_ws_broadcasts_order_created_and_updated(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)
    viewer = login(client, VIEWER_USERNAME, VIEWER_PASSWORD)

    with client.websocket_connect(f"{FDE}/ws?token={viewer['access_token']}") as websocket:
        assert websocket.receive_json()["type"] == "connected"

        order = _publish(client, enterprise, title="WebSocket 推送验证")
        created = websocket.receive_json()
        assert created["type"] == "order.created"
        assert set(created["order"]) == ORDER_FIELDS
        assert created["order"]["id"] == order["id"]
        assert created["order"]["status"] == "open"

        _claim(client, engineer, order["id"])
        claimed = websocket.receive_json()
        assert claimed["type"] == "order.updated"
        assert claimed["order"]["status"] == "in_progress"
        assert claimed["order"]["engineer"]["id"] == engineer["user"]["id"]

        _add_log(client, engineer, order["id"])
        logged = websocket.receive_json()
        assert logged["type"] == "order.updated"
        assert logged["order"]["work_log_count"] == 1

        client.post(f"{FDE}/orders/{order['id']}/complete", headers=_headers(enterprise))
        completed = websocket.receive_json()
        assert completed["type"] == "order.updated"
        assert completed["order"]["status"] == "completed"
        assert completed["order"]["escrow_status"] == "released"
