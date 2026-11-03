"""管理后台请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RedeemCodeStatus = Literal["active", "used", "disabled"]
RedeemCodeUpdateStatus = Literal["active", "disabled"]


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    balance_cents: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserUpdateRequest(BaseModel):
    """PATCH 用户：两个字段都可选，至少给一个才有实际效果。"""

    is_active: bool | None = None
    roles: list[str] | None = Field(default=None, min_length=1)


class RoleOptionResponse(BaseModel):
    name: str
    description: str | None


class RoleOptionListResponse(BaseModel):
    items: list[RoleOptionResponse]


class RedeemCodeUserRef(BaseModel):
    """兑换码使用人摘要。"""

    id: int
    display_name: str


class AdminRedeemCodeResponse(BaseModel):
    id: int
    code: str
    amount_cents: int
    status: RedeemCodeStatus
    batch_no: str
    note: str | None
    is_expired: bool
    used_by: RedeemCodeUserRef | None
    used_at: datetime | None
    expires_at: datetime | None
    created_at: datetime


class AdminRedeemCodeListResponse(BaseModel):
    items: list[AdminRedeemCodeResponse]
    total: int
    page: int
    page_size: int


class RedeemCodeCreateRequest(BaseModel):
    amount_cents: int = Field(ge=100, le=100_000_000)
    quantity: int = Field(ge=1, le=100)
    expires_in_days: int | None = Field(default=None, ge=1, le=3650)
    note: str | None = Field(default=None, max_length=120)


class RedeemCodeBatchResponse(BaseModel):
    batch_no: str
    items: list[AdminRedeemCodeResponse]


class RedeemCodeUpdateRequest(BaseModel):
    status: RedeemCodeUpdateStatus


class SettingItemResponse(BaseModel):
    key: str
    value: str
    updated_at: datetime | None


class SettingsListResponse(BaseModel):
    items: list[SettingItemResponse]


class SettingsUpdateRequest(BaseModel):
    # 至少提交一项，避免空 PATCH 产生无意义写入。
    values: dict[str, str] = Field(min_length=1)


__all__ = [
    "AdminRedeemCodeListResponse",
    "AdminRedeemCodeResponse",
    "AdminUserListResponse",
    "AdminUserResponse",
    "AdminUserUpdateRequest",
    "RedeemCodeBatchResponse",
    "RedeemCodeCreateRequest",
    "RedeemCodeStatus",
    "RedeemCodeUpdateRequest",
    "RedeemCodeUpdateStatus",
    "RedeemCodeUserRef",
    "RoleOptionListResponse",
    "RoleOptionResponse",
    "SettingItemResponse",
    "SettingsListResponse",
    "SettingsUpdateRequest",
]
