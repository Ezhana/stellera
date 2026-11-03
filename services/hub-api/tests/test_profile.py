"""个人资料与公开主页：读写、邮箱唯一、清空规则、合作记录与统计。"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

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
    register,
)

PROFILE = f"{API_V1}/profile"
PROFILES = f"{API_V1}/profiles"
FDE = f"{API_V1}/fde"

PROFILE_FIELDS = {
    "id",
    "username",
    "nickname",
    "email",
    "real_name",
    "bio",
    "skills",
    "city",
    "contact_phone",
    "contact_wechat",
    "roles",
    "certifications",
    "created_at",
    "cooperation",
}

PUBLIC_PROFILE_FIELDS = {
    "id",
    "nickname",
    "bio",
    "skills",
    "city",
    "certifications",
    "member_since",
    "cooperation",
}

COOPERATION_FIELDS = {
    "completed_count",
    "partner_count",
    "total_amount_cents",
    "records",
}

RECORD_FIELDS = {
    "order_id",
    "code",
    "title",
    "price_cents",
    "completed_at",
    "role",
    "counterpart",
}

COUNTERPART_FIELDS = {"id", "display_name", "certifications"}


def _headers(pair: dict[str, Any]) -> dict[str, str]:
    return auth_headers(pair["access_token"])


def _profile(client: TestClient, pair: dict[str, Any]) -> dict[str, Any]:
    response = client.get(PROFILE, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _public_profile(client: TestClient, pair: dict[str, Any], user_id: int) -> dict[str, Any]:
    response = client.get(f"{PROFILES}/{user_id}", headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _patch(client: TestClient, pair: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    response = client.patch(PROFILE, headers=_headers(pair), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _publish(client: TestClient, pair: dict[str, Any], *, price_cents: int = 1_000_000) -> dict:
    response = client.post(
        f"{FDE}/orders",
        headers=_headers(pair),
        json={
            "title": "合作记录测试订单",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 3,
            "price_cents": price_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _apply(client: TestClient, pair: dict[str, Any], order_id: int, *, kind: str) -> dict:
    response = client.post(
        f"{FDE}/orders/{order_id}/applications",
        headers=_headers(pair),
        json={"type": kind},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _approve(client: TestClient, pair: dict[str, Any], application_id: int) -> dict:
    response = client.post(
        f"{FDE}/applications/{application_id}/approve", headers=_headers(pair), json={}
    )
    assert response.status_code == 200, response.text
    return response.json()


def _complete_order(
    client: TestClient, publisher: dict[str, Any], engineer: dict[str, Any]
) -> dict:
    """发布 -> 申请接单 -> 通过 -> 申请交付 -> 通过，得到已完成订单。"""
    order = _publish(client, publisher)
    accepted = _apply(client, engineer, order["id"], kind="accept")
    _approve(client, publisher, accepted["id"])
    delivery = _apply(client, engineer, order["id"], kind="delivery")
    return _approve(client, publisher, delivery["id"])["order"]


# ---------- 认证 ----------


def test_profile_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(PROFILE).status_code == 401
    assert client.patch(PROFILE, json={"nickname": "x"}).status_code == 401
    assert client.get(f"{PROFILE}/certification-applications").status_code == 401
    assert (
        client.post(f"{PROFILE}/certification-applications", json={"type": "realname"}).status_code
        == 401
    )
    assert client.get(f"{PROFILES}/1").status_code == 401


# ---------- 本人资料 ----------


def test_get_own_profile(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    body = _profile(client, member)

    assert set(body) == PROFILE_FIELDS
    assert body["id"] == member["user"]["id"]
    assert body["username"] == MEMBER_USERNAME
    assert body["nickname"] == "会员（演示）"
    assert body["email"] == "member@example.com"
    # member 的实名申请仍是 pending，不能提前写入 full_name。
    assert body["real_name"] is None
    assert body["roles"] == ["member"]
    assert body["certifications"] == []
    assert body["bio"] is None
    assert body["skills"] is None
    assert body["city"] is None
    assert body["contact_phone"] is None
    assert body["contact_wechat"] is None
    cooperation = body["cooperation"]
    assert set(cooperation) == COOPERATION_FIELDS
    assert cooperation["completed_count"] == 0
    assert cooperation["partner_count"] == 0
    assert cooperation["total_amount_cents"] == 0
    assert cooperation["records"] == []


def test_enterprise_profile_has_real_name_and_certifications(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    body = _profile(client, enterprise)

    assert body["nickname"] == "企业（演示）"
    assert body["real_name"] == "张伟"
    assert body["roles"] == ["member", "realname", "enterprise"]
    assert body["certifications"] == ["realname", "enterprise"]

    cooperation = body["cooperation"]
    assert cooperation["completed_count"] == 2
    assert cooperation["partner_count"] == 1
    assert cooperation["total_amount_cents"] == 15_700_000
    records = cooperation["records"]
    assert len(records) == 2
    assert all(set(record) == RECORD_FIELDS for record in records)
    # 完成时间倒序：FDE-DEMO-0010（55 天前）在前。
    assert [record["code"] for record in records] == ["FDE-DEMO-0010", "FDE-DEMO-0009"]
    assert all(record["role"] == "publisher" for record in records)
    assert all(record["completed_at"] for record in records)
    counterpart = records[0]["counterpart"]
    assert set(counterpart) == COUNTERPART_FIELDS
    assert counterpart["display_name"] == "工程师（演示）"
    assert counterpart["certifications"] == ["realname", "engineer"]


def test_engineer_profile_cooperation_role(client: TestClient) -> None:
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)

    body = _profile(client, engineer)

    assert body["real_name"] == "李强"
    assert body["certifications"] == ["realname", "engineer"]
    cooperation = body["cooperation"]
    assert cooperation["completed_count"] == 2
    assert cooperation["partner_count"] == 1
    # 工程师角色而不是发布者角色，对方是企业（演示）。
    assert all(record["role"] == "engineer" for record in cooperation["records"])
    assert cooperation["records"][0]["counterpart"] == {
        "id": login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)["user"]["id"],
        "display_name": "企业（演示）",
        "certifications": ["realname", "enterprise"],
    }


def test_updated_profile_after_registration(client: TestClient) -> None:
    registered = register(client, "newbie")

    body = _profile(client, registered)

    assert body["username"] == "newbie"
    assert body["nickname"] == f"用户{registered['user']['id']:06d}"
    assert body["real_name"] is None
    assert body["roles"] == ["member"]
    assert body["certifications"] == []


# ---------- 修改资料 ----------


def test_update_profile_fields(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    body = _patch(
        client,
        member,
        {
            "nickname": "  数据标注小助手  ",
            "bio": "5 年数据标注与质检经验",
            "skills": "Python,数据标注",
            "city": "上海",
            "contact_phone": "13800000000",
            "contact_wechat": "stellera_member",
            "email": "  NewMember@Example.COM ",
        },
    )

    assert body["nickname"] == "数据标注小助手"
    assert body["bio"] == "5 年数据标注与质检经验"
    assert body["skills"] == "Python,数据标注"
    assert body["city"] == "上海"
    assert body["contact_phone"] == "13800000000"
    assert body["contact_wechat"] == "stellera_member"
    assert body["email"] == "newmember@example.com"
    # 昵称 / 邮箱可改，但实名与角色不变。
    assert body["real_name"] is None
    assert body["roles"] == ["member"]

    again = _profile(client, member)
    assert again["nickname"] == "数据标注小助手"
    assert again["email"] == "newmember@example.com"
    # 登录后 /auth/me 的昵称同步更新。
    me = client.get(f"{API_V1}/auth/me", headers=_headers(member)).json()
    assert me["nickname"] == "数据标注小助手"
    assert me["email"] == "newmember@example.com"


def test_clear_optional_profile_fields(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    _patch(
        client,
        member,
        {
            "bio": "介绍",
            "skills": "技能",
            "city": "北京",
            "contact_phone": "13900000000",
            "contact_wechat": "wechat",
        },
    )

    cleared = _patch(
        client,
        member,
        {
            "bio": "",
            "skills": "  ",
            "city": "",
            "contact_phone": "",
            "contact_wechat": "",
        },
    )

    assert cleared["bio"] is None
    assert cleared["skills"] is None
    assert cleared["city"] is None
    assert cleared["contact_phone"] is None
    assert cleared["contact_wechat"] is None
    # 昵称 / 邮箱不会被清空。
    assert cleared["nickname"] == "会员（演示）"
    assert cleared["email"] == "member@example.com"


def test_update_profile_email_conflict(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    for email in ("enterprise@example.com", "ENTERPRISE@example.com"):
        response = client.patch(PROFILE, headers=_headers(member), json={"email": email})
        assert response.status_code == 409
        assert response.json()["detail"] == "邮箱已被注册"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"nickname": ""},
        {"nickname": "x" * 65},
        {"email": ""},
        {"email": "not-an-email"},
        {"bio": "x" * 1001},
        {"skills": "x" * 256},
        {"city": "x" * 65},
        {"contact_phone": "1" * 33},
        {"contact_wechat": "x" * 65},
        # full_name（实名）与认证不在个人资料的可编辑字段里。
        {"full_name": "新实名"},
        {"certification": "enterprise"},
    ],
)
def test_update_profile_validation(client: TestClient, payload: dict[str, Any]) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.patch(PROFILE, headers=_headers(member), json=payload)

    assert response.status_code == 422, payload


def test_update_profile_cannot_edit_real_name(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    enterprise_id = enterprise["user"]["id"]

    _patch(client, member, {"nickname": "新昵称"})

    enterprise_body = _public_profile(client, member, enterprise_id)
    assert "real_name" not in enterprise_body
    # 企业实名由认证审核写入，不会被昵称等资料编辑覆盖。
    assert _profile(client, enterprise)["real_name"] == "张伟"


# ---------- 公开主页 ----------


def test_public_profile_hides_sensitive_fields(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)

    body = _public_profile(client, member, enterprise["user"]["id"])

    assert set(body) == PUBLIC_PROFILE_FIELDS
    for hidden in (
        "username",
        "email",
        "real_name",
        "contact_phone",
        "contact_wechat",
        "roles",
    ):
        assert hidden not in body
    assert body["nickname"] == "企业（演示）"
    assert body["certifications"] == ["realname", "enterprise"]
    assert body["member_since"]
    cooperation = body["cooperation"]
    assert set(cooperation) == COOPERATION_FIELDS
    assert cooperation["completed_count"] == 2
    counterpart = cooperation["records"][0]["counterpart"]
    assert set(counterpart) == COUNTERPART_FIELDS
    # 对方摘要同样只给展示名与认证。
    assert "email" not in counterpart
    assert "username" not in counterpart


def test_public_profile_of_member_has_no_certifications(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    member_id = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)["user"]["id"]

    body = _public_profile(client, enterprise, member_id)

    assert body["nickname"] == "会员（演示）"
    assert body["certifications"] == []
    assert body["cooperation"]["records"] == []


def test_public_profile_unknown_user_is_404(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{PROFILES}/999999", headers=_headers(member))

    assert response.status_code == 404


# ---------- 合作记录与统计 ----------


def test_cooperation_stats_after_completed_order(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    engineer = login(client, ENGINEER_USERNAME, ENGINEER_PASSWORD)

    completed = _complete_order(client, enterprise, engineer)

    body = _profile(client, enterprise)
    cooperation = body["cooperation"]
    assert cooperation["completed_count"] == 3
    assert cooperation["total_amount_cents"] == 16_700_000
    assert cooperation["partner_count"] == 1
    latest = cooperation["records"][0]
    assert latest["order_id"] == completed["id"]
    assert latest["role"] == "publisher"
    assert latest["counterpart"]["display_name"] == "工程师（演示）"

    engineer_body = _profile(client, engineer)
    assert engineer_body["cooperation"]["completed_count"] == 3
    assert engineer_body["cooperation"]["records"][0]["role"] == "engineer"
    assert (
        engineer_body["cooperation"]["records"][0]["counterpart"]["display_name"] == "企业（演示）"
    )


def test_cooperation_partner_count_counts_distinct_users(client: TestClient) -> None:
    enterprise = login(client, ENTERPRISE_USERNAME, ENTERPRISE_PASSWORD)
    helper = register(client, "cohelper")

    order = _publish(client, enterprise)
    accepted = _apply(client, helper, order["id"], kind="accept")
    _approve(client, enterprise, accepted["id"])
    delivery = _apply(client, helper, order["id"], kind="delivery")
    _approve(client, enterprise, delivery["id"])

    cooperation = _profile(client, enterprise)["cooperation"]
    assert cooperation["completed_count"] == 3
    # 工程师（演示）+ 新注册的 cohelper 两个不同合作方。
    assert cooperation["partner_count"] == 2
