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

# 部署模板（deploy/env/*.env.example）里的占位值前缀；非 development/test 环境必须替换。
PLACEHOLDER_PREFIXES = ("replace-", "change-me")
# 生产环境禁止的演示弱口令集合，与 deploy/env/*.env.example 里的演示账号口径保持一致。
DEMO_WEAK_PASSWORDS = frozenset(
    {
        "admin12345",
        "operator12345",
        "viewer12345",
        "enterprise12345",
        "engineer12345",
    }
)

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
        # 启动 fail-fast 的错误信息通常会进容器日志；不要把 JWT_SECRET/数据库口令等原始值打印出来。
        hide_input_in_errors=True,
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
        """启动即校验安全相关配置，避免带着模板占位值/演示弱口令上线。

        development/test 保持开箱可用（允许示例 JWT 与弱口令演示账号）；
        staging/production 拒绝模板占位值与过度宽松的配置。
        """
        if len(self.jwt_secret) < 32:
            raise ValueError(
                f"JWT_SECRET 至少需要 32 个字符（当前 {len(self.jwt_secret)} 个）；"
                "请用 `just gen-secret 32` 生成后写入环境变量"
            )

        if self.app_env in {"development", "test"}:
            return self

        if self.jwt_secret == DEFAULT_INSECURE_JWT_SECRET:
            raise ValueError(
                "非 development/test 环境必须显式设置 JWT_SECRET，不能使用本地开发示例值；"
                "请用 `just gen-secret 32` 生成后写入环境变量"
            )
        if self.jwt_secret.strip().lower().startswith(PLACEHOLDER_PREFIXES):
            raise ValueError(
                "JWT_SECRET 仍是部署模板里的占位值（replace-*/change-me*），"
                "非 development/test 环境必须替换；请用 `just gen-secret 32` 生成真实密钥"
            )
        database_url = self.database_url.strip().lower()
        if any(token in database_url for token in PLACEHOLDER_PREFIXES):
            raise ValueError(
                "DATABASE_URL 仍包含模板占位密码（replace-*/change-me*），"
                "非 development/test 环境必须替换；"
                "请用 `just gen-secret 32` 生成强密码并同步修改"
            )

        if self.app_env == "production":
            if self.seed_demo_users:
                raise ValueError(
                    "生产环境不允许 SEED_DEMO_USERS=true：会创建弱口令演示账号与演示订单；"
                    "请设置 SEED_DEMO_USERS=false"
                )
            seed_passwords = {
                "SEED_ADMIN_PASSWORD": self.seed_admin_password,
                "SEED_OPERATOR_PASSWORD": self.seed_operator_password,
                "SEED_VIEWER_PASSWORD": self.seed_viewer_password,
                "SEED_ENTERPRISE_PASSWORD": self.seed_enterprise_password,
                "SEED_ENGINEER_PASSWORD": self.seed_engineer_password,
            }
            weak_vars = [
                name for name, value in seed_passwords.items() if value in DEMO_WEAK_PASSWORDS
            ]
            if weak_vars:
                raise ValueError(
                    "生产环境不允许使用演示弱口令："
                    + "、".join(weak_vars)
                    + "；请用 `just gen-secret 32` 生成强口令后写入对应环境变量"
                )
        return self


def get_settings() -> Settings:
    """返回一份新的 Settings（便于测试用环境变量/参数覆盖）。"""
    return Settings()
