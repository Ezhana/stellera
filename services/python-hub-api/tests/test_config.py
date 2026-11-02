"""Settings 启动校验：staging/production 拒绝模板占位值与演示弱口令。

全部用 ``Settings(_env_file=None, ...)`` 构造，避免测试受服务目录下 .env 影响；
需要覆盖的字段都显式传入，环境变量不会改变断言结果。
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.core.config import (
    DEFAULT_INSECURE_JWT_SECRET,
    DEMO_WEAK_PASSWORDS,
    Settings,
)

VALID_JWT_SECRET = "staging-only-generated-secret-32-chars-0123456789"
VALID_DATABASE_URL = "postgresql+asyncpg://hub:generated-strong-password@db:5432/hub"
VALID_SEED_PASSWORDS: dict[str, str] = {
    "seed_admin_password": "Staging-Admin-Password-1",
    "seed_operator_password": "Staging-Operator-Password-1",
    "seed_viewer_password": "Staging-Viewer-Password-1",
    "seed_enterprise_password": "Staging-Enterprise-Password-1",
    "seed_engineer_password": "Staging-Engineer-Password-1",
}


def build_settings(**overrides: Any) -> Settings:
    """构造一份默认合法的 staging 配置，再叠加测试用例的覆盖项。"""
    values: dict[str, Any] = {
        "app_env": "staging",
        "jwt_secret": VALID_JWT_SECRET,
        "database_url": VALID_DATABASE_URL,
        "seed_demo_users": False,
        **VALID_SEED_PASSWORDS,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


# ---------- JWT_SECRET ----------


@pytest.mark.parametrize(
    "placeholder",
    [
        "replace-with-openssl-rand-hex-32",
        "REPLACE-WITH-openssl-rand-hex-32",
        "change-me-change-me-change-me-123456",
    ],
)
def test_staging_rejects_template_placeholder_jwt_secret(placeholder: str) -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET.*占位"):
        build_settings(jwt_secret=placeholder)


def test_staging_rejects_development_example_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        build_settings(jwt_secret=DEFAULT_INSECURE_JWT_SECRET)


def test_staging_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET.*32"):
        build_settings(jwt_secret="too-short-to-be-safe")


def test_staging_accepts_valid_config() -> None:
    settings = build_settings()

    assert settings.app_env == "staging"
    assert settings.jwt_secret == VALID_JWT_SECRET


def test_development_allows_default_example_jwt_secret() -> None:
    # 本地开发开箱即用：不额外传任何密钥时沿用示例值也能启动。
    settings = Settings(_env_file=None, app_env="development")

    assert settings.jwt_secret == DEFAULT_INSECURE_JWT_SECRET


# ---------- DATABASE_URL ----------


@pytest.mark.parametrize("app_env", ["staging", "production"])
@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+asyncpg://hub:replace-with-strong-password@db:5432/hub",
        "postgresql+asyncpg://hub:change-me-db-password@db:5432/hub",
    ],
)
def test_non_development_rejects_placeholder_database_url(app_env: str, database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL.*占位"):
        build_settings(app_env=app_env, database_url=database_url)


# ---------- production 演示数据 ----------


def test_production_rejects_seed_demo_users() -> None:
    with pytest.raises(ValidationError, match="SEED_DEMO_USERS"):
        build_settings(app_env="production", seed_demo_users=True)


@pytest.mark.parametrize(
    ("field_name", "weak_password", "env_name"),
    [
        ("seed_admin_password", "admin12345", "SEED_ADMIN_PASSWORD"),
        ("seed_operator_password", "operator12345", "SEED_OPERATOR_PASSWORD"),
        ("seed_viewer_password", "viewer12345", "SEED_VIEWER_PASSWORD"),
        ("seed_enterprise_password", "enterprise12345", "SEED_ENTERPRISE_PASSWORD"),
        ("seed_engineer_password", "engineer12345", "SEED_ENGINEER_PASSWORD"),
    ],
)
def test_production_rejects_demo_weak_seed_password(
    field_name: str, weak_password: str, env_name: str
) -> None:
    assert weak_password in DEMO_WEAK_PASSWORDS

    with pytest.raises(ValidationError, match=env_name):
        build_settings(app_env="production", **{field_name: weak_password})


def test_production_accepts_valid_config() -> None:
    settings = build_settings(app_env="production")

    assert settings.app_env == "production"
    assert settings.seed_demo_users is False
