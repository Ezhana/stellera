"""健康检查与公开文档端点。"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_reports_database_and_rbac(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"] == {"database": "ok", "rbac": "ok"}


def test_docs_are_public(client: TestClient) -> None:
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_unknown_path_is_not_public(client: TestClient) -> None:
    # 未在任何策略里的路径，匿名访问应被 Casbin 拦住返回 401（而不是暴露 404）。
    response = client.get("/api/v1/unknown")
    assert response.status_code == 401
