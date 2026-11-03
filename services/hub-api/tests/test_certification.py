"""三类认证申请与管理员审核：校验、冲突、角色替换、自动驳回与摘要同步。"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db import create_engine, create_session_factory
from app.models.certification import CertificationApplication
from tests.conftest import (
    API_V1,
    MEMBER_PASSWORD,
    MEMBER_USERNAME,
    auth_headers,
    login,
    register,
)

PROFILE = f"{API_V1}/profile"
CERT_APPLICATIONS = f"{PROFILE}/certification-applications"
PROFILES = f"{API_V1}/profiles"
ADMIN = f"{API_V1}/admin"
ADMIN_APPLICATIONS = f"{ADMIN}/certification-applications"
FDE = f"{API_V1}/fde"

APPLICATION_FIELDS = {
    "id",
    "type",
    "status",
    "real_name",
    "id_number",
    "contact_phone",
    "company_name",
    "credit_code",
    "contact_name",
    "skills",
    "work_years",
    "project_experience",
    "description",
    "review_note",
    "reviewer",
    "reviewed_at",
    "created_at",
}

REALNAME_PAYLOAD = {
    "type": "realname",
    "real_name": "测试用户",
    "id_number": "110101199001011234",
    "contact_phone": "13600000000",
    "description": "用于测试实名认证",
}
ENTERPRISE_PAYLOAD = {
    "type": "enterprise",
    "company_name": "测试科技有限公司",
    "credit_code": "91310000MA1FL0TEST",
    "contact_name": "测试用户",
    "contact_phone": "13600000000",
    "description": "用于测试企业认证",
}
ENGINEER_PAYLOAD = {
    "type": "engineer",
    "skills": "Python,数据标注",
    "work_years": 5,
    "project_experience": "主导 2 个数据标注交付项目。",
    "contact_phone": "13600000000",
}


def _headers(pair: dict[str, Any]) -> dict[str, str]:
    return auth_headers(pair["access_token"])


def _submit(client: TestClient, pair: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    response = client.post(CERT_APPLICATIONS, headers=_headers(pair), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _my_applications(client: TestClient, pair: dict[str, Any]) -> list[dict[str, Any]]:
    response = client.get(CERT_APPLICATIONS, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _approve(
    client: TestClient,
    admin: dict[str, Any],
    application_id: int,
    *,
    note: str | None = "审核通过",
) -> dict[str, Any]:
    response = client.post(
        f"{ADMIN_APPLICATIONS}/{application_id}/approve",
        headers=_headers(admin),
        json={"note": note},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _reject(
    client: TestClient,
    admin: dict[str, Any],
    application_id: int,
    *,
    note: str | None = "资料不完整",
) -> dict[str, Any]:
    response = client.post(
        f"{ADMIN_APPLICATIONS}/{application_id}/reject",
        headers=_headers(admin),
        json={"note": note},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _approve_realname(
    client: TestClient, user: dict[str, Any], admin: dict[str, Any]
) -> dict[str, Any]:
    application = _submit(client, user, REALNAME_PAYLOAD)
    return _approve(client, admin, application["id"])


def _profile(client: TestClient, pair: dict[str, Any]) -> dict[str, Any]:
    response = client.get(PROFILE, headers=_headers(pair))
    assert response.status_code == 200, response.text
    return response.json()


def _admin_application_list(
    client: TestClient, admin: dict[str, Any], **params: str | int
) -> dict[str, Any]:
    response = client.get(ADMIN_APPLICATIONS, headers=_headers(admin), params=params)
    assert response.status_code == 200, response.text
    return response.json()


# ---------- 权限 ----------


def test_certification_endpoints_require_authentication(client: TestClient) -> None:
    assert client.get(CERT_APPLICATIONS).status_code == 401
    assert client.post(CERT_APPLICATIONS, json=REALNAME_PAYLOAD).status_code == 401
    assert client.get(ADMIN_APPLICATIONS).status_code == 401
    assert client.post(f"{ADMIN_APPLICATIONS}/1/approve", json={}).status_code == 401
    assert client.post(f"{ADMIN_APPLICATIONS}/1/reject", json={}).status_code == 401


def test_non_admin_cannot_review_certifications(client: TestClient) -> None:
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    assert client.get(ADMIN_APPLICATIONS, headers=_headers(member)).status_code == 403
    assert (
        client.post(
            f"{ADMIN_APPLICATIONS}/1/approve", headers=_headers(member), json={}
        ).status_code
        == 403
    )
    assert (
        client.post(f"{ADMIN_APPLICATIONS}/1/reject", headers=_headers(member), json={}).status_code
        == 403
    )


# ---------- 提交与校验 ----------


def test_realname_application_flow(client: TestClient) -> None:
    user = register(client, "certuser")

    application = _submit(client, user, REALNAME_PAYLOAD)

    assert set(application) == APPLICATION_FIELDS
    assert application["type"] == "realname"
    assert application["status"] == "pending"
    assert application["real_name"] == "测试用户"
    assert application["id_number"] == "110101199001011234"
    assert application["reviewer"] is None
    assert application["reviewed_at"] is None

    items = _my_applications(client, user)
    assert [item["id"] for item in items] == [application["id"]]

    # 审核前认证与实名都不生效。
    profile = _profile(client, user)
    assert profile["certifications"] == []
    assert profile["real_name"] is None

    duplicate = client.post(CERT_APPLICATIONS, headers=_headers(user), json=REALNAME_PAYLOAD)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "该类型认证正在审核中"


def test_application_list_only_contains_own_applications(client: TestClient) -> None:
    alice = register(client, "alice")
    bob = register(client, "bob")
    _submit(client, alice, REALNAME_PAYLOAD)

    alice_items = _my_applications(client, alice)
    assert len(alice_items) == 1
    assert _my_applications(client, bob) == []


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "realname", "real_name": "测试用户"},
        {"type": "realname", "real_name": "测试用户", "id_number": "1"},
        {"type": "unknown"},
        {**REALNAME_PAYLOAD, "description": "x" * 2001},
        {**REALNAME_PAYLOAD, "id_number": "x" * 65},
    ],
)
def test_certification_application_validation(client: TestClient, payload: dict[str, Any]) -> None:
    user = register(client, "validator")

    response = client.post(CERT_APPLICATIONS, headers=_headers(user), json=payload)

    assert response.status_code == 422, payload


def test_business_application_required_fields(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "business_fields")
    _approve_realname(client, user, admin)

    payloads = [
        {"type": "enterprise", "company_name": "测试公司"},
        {**ENTERPRISE_PAYLOAD, "contact_name": None},
        {"type": "engineer", "skills": "Python", "work_years": 5},
        {"type": "engineer", "skills": "x", "work_years": 61, "project_experience": "项目"},
    ]
    for payload in payloads:
        response = client.post(CERT_APPLICATIONS, headers=_headers(user), json=payload)
        assert response.status_code == 422, payload


def test_enterprise_and_engineer_require_realname(client: TestClient) -> None:
    user = register(client, "unverified")

    for payload in (ENTERPRISE_PAYLOAD, ENGINEER_PAYLOAD):
        response = client.post(CERT_APPLICATIONS, headers=_headers(user), json=payload)
        assert response.status_code == 409
        assert response.json()["detail"] == "请先完成实名认证"


# ---------- 审核通过 ----------


def test_approve_realname_writes_full_name_and_role(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "realname_user")

    approved = _approve_realname(client, user, admin)

    assert approved["status"] == "approved"
    assert approved["review_note"] == "审核通过"
    assert approved["reviewed_at"] is not None
    assert approved["reviewer"] == {
        "id": admin["user"]["id"],
        "display_name": "管理员",
        "certifications": [],
    }

    profile = _profile(client, user)
    assert profile["real_name"] == "测试用户"
    assert profile["roles"] == ["member", "realname"]
    assert profile["certifications"] == ["realname"]
    me = client.get(f"{API_V1}/auth/me", headers=_headers(user)).json()
    assert set(me["roles"]) == {"member", "realname"}
    assert me["certifications"] == ["realname"]

    # realname 通过后不能再申请同类型认证。
    again = client.post(CERT_APPLICATIONS, headers=_headers(user), json=REALNAME_PAYLOAD)
    assert again.status_code == 409
    assert again.json()["detail"] == "该类型认证已通过"


def test_approve_enterprise_and_engineer_replace_each_other(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "business_user")
    _approve_realname(client, user, admin)

    enterprise = _submit(client, user, ENTERPRISE_PAYLOAD)
    approved_enterprise = _approve(client, admin, enterprise["id"])

    assert approved_enterprise["status"] == "approved"
    assert approved_enterprise["company_name"] == "测试科技有限公司"
    assert approved_enterprise["user"]["certifications"] == ["realname", "enterprise"]
    profile = _profile(client, user)
    assert profile["roles"] == ["member", "realname", "enterprise"]
    assert profile["certifications"] == ["realname", "enterprise"]

    # 企业认证已通过后不能重复申请。
    duplicate = client.post(CERT_APPLICATIONS, headers=_headers(user), json=ENTERPRISE_PAYLOAD)
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "该类型认证已通过"

    # 改申请工程师并审核通过：企业角色被替换，实名保留。
    engineer = _submit(client, user, ENGINEER_PAYLOAD)
    approved_engineer = _approve(client, admin, engineer["id"])
    assert approved_engineer["status"] == "approved"
    profile = _profile(client, user)
    assert profile["roles"] == ["member", "realname", "engineer"]
    assert profile["certifications"] == ["realname", "engineer"]

    # 订单用户摘要同步为最新认证列表。
    adjusted = client.post(
        f"{ADMIN}/users/{user['user']['id']}/wallet-adjustments",
        headers=_headers(admin),
        json={"direction": "credit", "amount_cents": 100_000, "note": "认证后发布订单"},
    )
    assert adjusted.status_code == 200
    order = client.post(
        f"{FDE}/orders",
        headers=_headers(user),
        json={
            "title": "认证后发布的订单",
            "industry": "医疗健康",
            "description": "",
            "delivery_days": 3,
            "price_cents": 10_000,
        },
    )
    assert order.status_code == 201, order.text
    assert order.json()["publisher"]["certifications"] == ["realname", "engineer"]
    assert order.json()["publisher"]["display_name"] == "用户" + f"{user['user']['id']:06d}"


def test_approving_business_application_rejects_other_pending(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "mutex_user")
    _approve_realname(client, user, admin)

    enterprise = _submit(client, user, ENTERPRISE_PAYLOAD)
    engineer = _submit(client, user, ENGINEER_PAYLOAD)

    approved = _approve(client, admin, enterprise["id"])
    assert approved["status"] == "approved"

    applications = {item["id"]: item for item in _my_applications(client, user)}
    rejected = applications[engineer["id"]]
    assert rejected["status"] == "rejected"
    assert rejected["review_note"] == "已通过其他认证"
    assert rejected["reviewer"]["display_name"] == "管理员"
    assert rejected["reviewed_at"] is not None

    # 已被自动驳回的申请不能再审批。
    again = client.post(
        f"{ADMIN_APPLICATIONS}/{engineer['id']}/approve", headers=_headers(admin), json={}
    )
    assert again.status_code == 409


def _insert_pending_enterprise_application(settings: Settings, user_id: int) -> int:
    """直接写库造一条 pending 企业申请，模拟绕过「先实名」校验的历史数据。"""

    async def _run() -> int:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                application = CertificationApplication(
                    user_id=user_id,
                    type="enterprise",
                    status="pending",
                    company_name="测试科技有限公司",
                    credit_code="91310000MA1FL0TEST",
                    contact_name="测试用户",
                    contact_phone="13600000000",
                )
                session.add(application)
                await session.commit()
                return application.id
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def test_approve_enterprise_without_realname_conflicts(
    settings: Settings, client: TestClient
) -> None:
    """服务层兜底：没有实名认证时审核通过企业认证应返回 409。"""
    admin = login(client)
    user = register(client, "bypass_user")
    application_id = _insert_pending_enterprise_application(settings, user["user"]["id"])

    response = client.post(
        f"{ADMIN_APPLICATIONS}/{application_id}/approve", headers=_headers(admin), json={}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "请先完成实名认证"


# ---------- 驳回 ----------


def test_reject_application_and_resubmit(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "rejected_user")
    application = _submit(client, user, REALNAME_PAYLOAD)

    rejected = _reject(client, admin, application["id"])

    assert rejected["status"] == "rejected"
    assert rejected["review_note"] == "资料不完整"
    assert rejected["reviewer"]["display_name"] == "管理员"
    assert rejected["reviewed_at"] is not None
    profile = _profile(client, user)
    assert profile["real_name"] is None
    assert profile["certifications"] == []

    # 驳回后可以重新提交新申请。
    resubmitted = _submit(client, user, REALNAME_PAYLOAD)
    assert resubmitted["status"] == "pending"
    assert resubmitted["id"] != application["id"]
    approved = _approve(client, admin, resubmitted["id"])
    assert approved["status"] == "approved"


def test_reject_processed_application_conflicts(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "processed_user")
    application = _submit(client, user, REALNAME_PAYLOAD)
    _approve(client, admin, application["id"])

    response = client.post(
        f"{ADMIN_APPLICATIONS}/{application['id']}/reject", headers=_headers(admin), json={}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "申请已处理，无法重复审批"


def test_unknown_application_is_404(client: TestClient) -> None:
    admin = login(client)

    for path in ("approve", "reject"):
        response = client.post(
            f"{ADMIN_APPLICATIONS}/999999/{path}", headers=_headers(admin), json={}
        )
        assert response.status_code == 404


# ---------- 管理端列表 ----------


def test_admin_application_list_filters(client: TestClient) -> None:
    admin = login(client)

    body = _admin_application_list(client, admin)
    assert set(body) == {"items", "total", "page", "page_size"}
    # 演示数据：企业/工程师各 2 条已通过 + member 1 条 pending。
    assert body["total"] == 5
    item = body["items"][0]
    assert set(item) == APPLICATION_FIELDS | {"user"}
    assert set(item["user"]) == {
        "id",
        "username",
        "nickname",
        "email",
        "roles",
        "certifications",
    }

    pending = _admin_application_list(client, admin, status="pending")
    assert pending["total"] == 1
    assert pending["items"][0]["type"] == "realname"
    assert pending["items"][0]["user"]["username"] == MEMBER_USERNAME
    assert pending["items"][0]["user"]["nickname"] == "会员（演示）"
    assert pending["items"][0]["user"]["certifications"] == []

    realname_apps = _admin_application_list(client, admin, type="realname", page_size=100)
    assert realname_apps["total"] == 3

    by_username = _admin_application_list(client, admin, q="engineer", page_size=100)
    assert by_username["total"] == 2
    assert {item["user"]["username"] for item in by_username["items"]} == {"engineer"}

    by_nickname = _admin_application_list(client, admin, q="企业", page_size=100)
    assert by_nickname["total"] == 2

    by_company = _admin_application_list(client, admin, q="智联", page_size=100)
    assert by_company["total"] == 1
    assert by_company["items"][0]["type"] == "enterprise"

    first_page = _admin_application_list(client, admin, page=1, page_size=2)
    second_page = _admin_application_list(client, admin, page=2, page_size=2)
    assert first_page["total"] == 5
    assert len(first_page["items"]) == len(second_page["items"]) == 2
    assert {item["id"] for item in first_page["items"]}.isdisjoint(
        {item["id"] for item in second_page["items"]}
    )


def test_admin_application_list_query_validation(client: TestClient) -> None:
    admin = login(client)

    for params in ({"status": "unknown"}, {"type": "unknown"}, {"page": 0}, {"page_size": 101}):
        response = client.get(ADMIN_APPLICATIONS, headers=_headers(admin), params=params)
        assert response.status_code == 422, params


def test_admin_can_approve_demo_member_pending_realname(client: TestClient) -> None:
    admin = login(client)
    pending = _admin_application_list(client, admin, status="pending")["items"]
    assert len(pending) == 1
    application = pending[0]

    approved = _approve(client, admin, application["id"], note="演示实名审核通过")

    assert approved["status"] == "approved"
    assert approved["real_name"] == "王芳"
    member = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)
    profile = _profile(client, member)
    assert profile["real_name"] == "王芳"
    assert profile["certifications"] == ["realname"]
    assert profile["roles"] == ["member", "realname"]

    # 已处理的申请不能重复审批。
    again = client.post(
        f"{ADMIN_APPLICATIONS}/{application['id']}/approve", headers=_headers(admin), json={}
    )
    assert again.status_code == 409


def test_public_profile_reflects_approved_certifications(client: TestClient) -> None:
    admin = login(client)
    user = register(client, "public_user")
    _approve_realname(client, user, admin)
    enterprise = _submit(client, user, ENTERPRISE_PAYLOAD)
    _approve(client, admin, enterprise["id"])
    viewer = login(client, MEMBER_USERNAME, MEMBER_PASSWORD)

    response = client.get(f"{PROFILES}/{user['user']['id']}", headers=_headers(viewer))

    assert response.status_code == 200
    body = response.json()
    assert body["nickname"] == f"用户{user['user']['id']:06d}"
    assert body["certifications"] == ["realname", "enterprise"]
