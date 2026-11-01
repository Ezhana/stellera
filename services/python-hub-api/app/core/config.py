"""应用配置：所有环境变量经 pydantic-settings 统一收口。

变量名与 `infra/compose.yaml`、`.env.example` 保持一致；除 `CASBIN_MODEL_PATH`
这类通常不需要改的内部路径外，不要把配置直接散落在业务代码里读环境变量。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_INSECURE_JWT_SECRET = "local-dev-only-change-me-32-characters-min"

# 服务根目录：app/core/config.py -> app/core -> app -> <service root>
SERVICE_ROOT = Path(__file__).resolve().parents[2]


def default_casbin_model_path() -> Path:
    """按优先级定位 casbin/model.conf：

    1. 当前工作目录下的 casbin/model.conf（源码目录 / Docker 工作目录 /app）；
    2. 服务根目录下的 casbin/model.conf（从任意 cwd 启动时）；
    3. 安装后的包内副本 app/rbac/model.conf（wheel 安装场景）。
    """
    cwd_candidate = Path("casbin/model.conf")
    if cwd_candidate.is_file():
        return cwd_candidate.resolve()
    source_candidate = SERVICE_ROOT / "casbin" / "model.conf"
    if source_candidate.is_file():
        return source_candidate
    return Path(__file__).resolve().parents[1] / "rbac" / "model.conf"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------- 运行环境 ----------
    app_env: Literal["development", "test", "staging", "production"] = "development"
    debug: bool = False
    docs_enabled: bool = True

    # ---------- 数据库 ----------
    # 默认值与 infra/.env.example 一致，方便本地只起 db 容器后直接 uv run。
    database_url: str = "postgresql+asyncpg://hub:hub_dev_password@localhost:5432/hub"
    database_echo: bool = False

    # ---------- JWT ----------
    jwt_secret: str = DEFAULT_INSECURE_JWT_SECRET
    jwt_issuer: str = "stellera-hub"
    jwt_audience: str = "stellera-hub-web"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800

    # ---------- HTTP ----------
    # 环境变量用逗号分隔；NoDecode 阻止 pydantic-settings 先把字符串当 JSON 解析，
    # 再由下面的 validator 切分，兼容 compose 里的 "a,b" 写法。
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    # ---------- Casbin ----------
    casbin_model_path: Path = default_casbin_model_path()

    # ---------- 种子数据 ----------
    seed_admin_username: str = "admin"
    seed_admin_email: str = "admin@example.com"
    seed_admin_password: str = "admin12345"
    seed_demo_users: bool = True
    seed_operator_password: str = "operator12345"
    seed_viewer_password: str = "viewer12345"
    # FDE 模块的两个演示账号：企业发布方与接单工程师。
    seed_enterprise_password: str = "enterprise12345"
    seed_engineer_password: str = "engineer12345"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def _validate_security_settings(self) -> Settings:
        if len(self.jwt_secret) < 32:
            raise ValueError("JWT_SECRET 至少需要 32 个字符")
        if self.app_env not in {"development", "test"}:
            if self.jwt_secret == DEFAULT_INSECURE_JWT_SECRET:
                raise ValueError("非 development 环境必须显式设置 JWT_SECRET，不能使用示例值")
        return self


def get_settings() -> Settings:
    """返回一份新的 Settings（便于测试用环境变量/参数覆盖）。"""
    return Settings()
