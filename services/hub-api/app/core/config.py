"""应用配置：运行时环境变量经 pydantic-settings 统一收口。

变量名与 `.env.example`、`compose.yml` 保持一致；除 `CASBIN_MODEL_PATH`
这类通常不需要改的内部路径外，不要把配置直接散落在业务代码里读环境变量。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
        # 启动错误的上下文里不要出现 JWT_SECRET / 数据库口令的原始值。
        hide_input_in_errors=True,
    )

    # ---------- 运行环境 ----------
    app_env: Literal["development", "test", "staging", "production"] = "development"
    # 调试子开关，逗号分隔；由使用方显式判断，例如 app.db 里的 "db_echo"。
    debug: Annotated[list[str], NoDecode] = []
    docs_enabled: bool = True

    # ---------- 数据库 ----------
    database_url: str = "postgresql+asyncpg://hub:hub_dev_password@localhost:5432/hub"

    # ---------- JWT ----------
    # 开发默认值；非 development 环境由部署层覆盖。
    jwt_secret: str = "local-dev-only-change-me-32-characters-min"
    jwt_issuer: str = "stellera-hub"
    jwt_audience: str = "stellera-hub-web"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 604800

    # ---------- HTTP ----------
    # 逗号分隔；NoDecode 阻止 pydantic-settings 先按 JSON 解析，交给下面的 validator 切分。
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    # ---------- Casbin ----------
    casbin_model_path: Path = default_casbin_model_path()

    @field_validator("debug", "cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


def get_settings() -> Settings:
    """返回一份新的 Settings（便于测试用环境变量/参数覆盖）。"""
    return Settings()
