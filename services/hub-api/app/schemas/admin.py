"""管理后台请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

RedeemCodeStatus = Literal["active", "used", "disabled"]
RedeemCodeUpdateStatus = Literal["active", "disabled"]
AdjustmentDirection = Literal["credit", "debit"]


class AdminUserResponse(BaseModel):
    id: int
    username: str
    nickname: str
    # full_name 是实名，只由实名认证审核通过时写入，管理端不可编辑。
    full_name: str | None
    email: str
    is_active: bool
    roles: list[str]
    # 认证列表由角色派生，顺序固定为 realname、enterprise、engineer。
    certifications: list[str]
    balance_cents: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserUpdateRequest(BaseModel):
    """PATCH 用户：只允许改昵称 / 邮箱 / 启用状态，至少一项。"""

    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    is_active: bool | None = None

    @field_validator("nickname", "email", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str | None) -> str | None:
        if value is not None and (
            not value
            or "@" not in value
            or value.startswith("@")
            or value.endswith("@")
            or any(char.isspace() for char in value)
        ):
            raise ValueError("邮箱格式不正确")
        return value

    @model_validator(mode="after")
    def _require_at_least_one(self) -> AdminUserUpdateRequest:
        if self.nickname is None and self.email is None and self.is_active is None:
            raise ValueError("至少需要修改一项")
        return self


class WalletAdjustmentRequest(BaseModel):
    """管理员余额调整：必须走钱包流水，不能直接改余额字段。"""

    direction: AdjustmentDirection
    amount_cents: int = Field(ge=1, le=100_000_000)
    note: str = Field(min_length=1, max_length=120)

    @field_validator("note", mode="before")
    @classmethod
    def _strip_note(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


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
    "AdjustmentDirection",
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
    "WalletAdjustmentRequest",
]
