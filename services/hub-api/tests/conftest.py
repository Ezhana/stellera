"""测试基线：临时 SQLite + TestClient，不依赖 Docker/PostgreSQL。

种子数据必须在进入 TestClient（触发 lifespan 里的 Casbin 投影）之前写入。
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import SERVICE_ROOT, Settings
from app.db import create_all_tables, create_engine, create_session_factory
from app.main import create_app
from app.scripts.seed import SeedSettings, seed_database

API_V1 = "/api/v1"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin12345"
MEMBER_USERNAME = "member"
MEMBER_PASSWORD = "member12345"
ENTERPRISE_USERNAME = "enterprise"
ENTERPRISE_PASSWORD = "enterprise12345"
ENGINEER_USERNAME = "engineer"
ENGINEER_PASSWORD = "engineer12345"


def build_test_settings(database_url: str) -> Settings:
    return Settings(
        app_env="test",
        debug=[],
        docs_enabled=True,
        database_url=database_url,
        jwt_secret="test-secret-key-with-at-least-32-characters",
        jwt_issuer="stellera-hub-test",
        jwt_audience="stellera-hub-web-test",
        access_token_ttl_seconds=300,
        refresh_token_ttl_seconds=3600,
        cors_origins=["http://testserver", "http://localhost:5173"],
        casbin_model_path=SERVICE_ROOT / "casbin" / "model.conf",
    )


def build_seed_settings() -> SeedSettings:
    return SeedSettings(
        _env_file=None,
        admin_username=ADMIN_USERNAME,
        admin_email="admin@example.com",
        admin_password=ADMIN_PASSWORD,
    )


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'hub-test.db'}")


async def prepare_database(settings: Settings) -> None:
    engine = create_engine(settings)
    try:
        await create_all_tables(engine)
        await seed_database(build_seed_settings(), create_session_factory(engine), demo=True)
    finally:
        await engine.dispose()


@pytest.fixture()
def app(settings: Settings):
    asyncio.run(prepare_database(settings))
    return create_app(settings)


@pytest.fixture()
def client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def login(
    client: TestClient, username: str = ADMIN_USERNAME, password: str = ADMIN_PASSWORD
) -> dict:
    response = client.post(
        f"{API_V1}/auth/login", json={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
