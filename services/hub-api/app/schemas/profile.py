"""个人信息、公开主页与认证申请的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.fde import OrderUserRef

CertificationType = Literal["realname", "enterprise", "engineer"]
CertificationStatus = Literal["pending", "approved", "rejected"]
CooperationRole = Literal["publisher", "engineer"]


class CooperationCounterpart(BaseModel):
    """合作记录里的对方摘要：只给 id、展示名与认证，不暴露联系方式。"""

    id: int
    display_name: str
    certifications: list[str]


class CooperationRecordResponse(BaseModel):
    order_id: int
    code: str
    title: str
    price_cents: int
    completed_at: datetime | None
    role: CooperationRole
    counterpart: CooperationCounterpart | None


class CooperationResponse(BaseModel):
    completed_count: int
    partner_count: int
    total_amount_cents: int
    records: list[CooperationRecordResponse]


class ProfileResponse(BaseModel):
    """本人资料：含邮箱、实名与联系方式。"""

    id: int
    username: str
    nickname: str
    email: str
    real_name: str | None
    bio: str | None
    skills: str | None
    city: str | None
    contact_phone: str | None
    contact_wechat: str | None
    roles: list[str]
    certifications: list[str]
    created_at: datetime
    cooperation: CooperationResponse


class PublicProfileResponse(BaseModel):
    """公开主页：隐藏 username / email / real_name / contact / roles。"""

    id: int
    nickname: str
    bio: str | None
    skills: str | None
    city: str | None
    certifications: list[str]
    member_since: datetime
    cooperation: CooperationResponse


class ProfileUpdateRequest(BaseModel):
    """PATCH 本人资料：字段全部可选，至少一项；空字符串清空（昵称 / 邮箱不可清空）。"""

    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=320)
    bio: str | None = Field(default=None, max_length=1000)
    skills: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_wechat: str | None = Field(default=None, max_length=64)

    @field_validator(
        "nickname",
        "email",
        "bio",
        "skills",
        "city",
        "contact_phone",
        "contact_wechat",
        mode="before",
    )
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
    def _require_at_least_one(self) -> ProfileUpdateRequest:
        fields = (
            self.nickname,
            self.email,
            self.bio,
            self.skills,
            self.city,
            self.contact_phone,
            self.contact_wechat,
        )
        if all(value is None for value in fields):
            raise ValueError("至少需要修改一项")
        return self


class CertificationApplicationCreateRequest(BaseModel):
    """提交认证申请：字段按类型必填（服务层校验），长度上限统一在这里限制。"""

    type: CertificationType
    real_name: str | None = Field(default=None, max_length=128)
    id_number: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=128)
    credit_code: str | None = Field(default=None, max_length=64)
    contact_name: str | None = Field(default=None, max_length=64)
    skills: str | None = Field(default=None, max_length=255)
    work_years: int | None = Field(default=None, ge=0, le=60)
    project_experience: str | None = Field(default=None, max_length=2000)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator(
        "real_name",
        "id_number",
        "contact_phone",
        "company_name",
        "credit_code",
        "contact_name",
        "skills",
        "project_experience",
        "description",
        mode="before",
    )
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class CertificationApplicationResponse(BaseModel):
    id: int
    type: CertificationType
    status: CertificationStatus
    real_name: str | None
    id_number: str | None
    contact_phone: str | None
    company_name: str | None
    credit_code: str | None
    contact_name: str | None
    skills: str | None
    work_years: int | None
    project_experience: str | None
    description: str | None
    review_note: str | None
    reviewer: OrderUserRef | None
    reviewed_at: datetime | None
    created_at: datetime


class CertificationApplicationListResponse(BaseModel):
    items: list[CertificationApplicationResponse]


class CertificationUserRef(BaseModel):
    """管理端认证申请里的申请人摘要。"""

    id: int
    username: str
    nickname: str
    email: str
    roles: list[str]
    certifications: list[str]


class AdminCertificationApplicationResponse(CertificationApplicationResponse):
    user: CertificationUserRef


class AdminCertificationApplicationListResponse(BaseModel):
    items: list[AdminCertificationApplicationResponse]
    total: int
    page: int
    page_size: int


class CertificationReviewRequest(BaseModel):
    """审核认证申请时可选的审批意见。"""

    note: str | None = Field(default=None, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def _strip_note(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


__all__ = [
    "AdminCertificationApplicationListResponse",
    "AdminCertificationApplicationResponse",
    "CertificationApplicationCreateRequest",
    "CertificationApplicationListResponse",
    "CertificationApplicationResponse",
    "CertificationReviewRequest",
    "CertificationStatus",
    "CertificationType",
    "CertificationUserRef",
    "CooperationCounterpart",
    "CooperationRecordResponse",
    "CooperationResponse",
    "CooperationRole",
    "ProfileResponse",
    "ProfileUpdateRequest",
    "PublicProfileResponse",
]
