"""管理后台请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.fde import Certification

RedeemCodeStatus = Literal["active", "used", "disabled"]
RedeemCodeUpdateStatus = Literal["active", "disabled"]
# 管理员可设置的认证状态：none 表示撤销企业 / 工程师认证。
CertificationChoice = Literal["none", "enterprise", "engineer"]
AdjustmentDirection = Literal["credit", "debit"]


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: str | None
    is_active: bool
    roles: list[str]
    # 认证状态由角色派生：enterprise / engineer / null。
    certification: Certification | None
    balance_cents: int
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int
    page: int
    page_size: int


class AdminUserUpdateRequest(BaseModel):
    """PATCH 用户：字段全部可选，但至少要修改一项；角色只能通过 certification 间接调整。"""

    full_name: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=320)
    is_active: bool | None = None
    certification: CertificationChoice | None = None

    @field_validator("full_name", mode="before")
    @classmethod
    def _strip_full_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("email", mode="before")
    @classmethod
    def _normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

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
        if (
            self.full_name is None
            and self.email is None
            and self.is_active is None
            and self.certification is None
        ):
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
    "CertificationChoice",
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
