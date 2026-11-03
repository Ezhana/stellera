"""认证相关请求/响应模型。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class RegisterRequest(BaseModel):
    """公开注册：用户名 / 邮箱统一小写，注册成功即获得 member 角色。"""

    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")
    email: str = Field(max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username", "email", mode="before")
    @classmethod
    def _normalize_identity(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("full_name", mode="before")
    @classmethod
    def _strip_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class PermissionItem(BaseModel):
    """Casbin 隐式权限的一条 (object, action) 记录，供前端权限卡片展示。"""

    object: str
    action: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    # 便于前端在过期前主动刷新，避免多一次 401 往返。
    expires_in: int
    refresh_expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    # 该用户经角色继承后的全部 Casbin 隐式权限（去重、按 object/action 排序）。
    permissions: list[PermissionItem]


class AuthResponse(TokenResponse):
    """登录响应：令牌 + 当前用户（与 GET /auth/me 相同结构）。"""

    user: UserResponse


__all__ = [
    "AuthResponse",
    "LoginRequest",
    "PermissionItem",
    "RefreshRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
]
