"""FDE 订单相关请求/响应模型。

字段与前端 BFF 契约一一对应；时间统一由服务层转成 UTC 后序列化。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderStatus = Literal["open", "in_progress", "completed", "cancelled"]
EscrowStatus = Literal["held", "released", "refunded"]
# 认证状态完全由角色派生：enterprise / engineer；未认证为 null。
Certification = Literal["enterprise", "engineer"]

ApplicationType = Literal["accept", "delivery"]
ApplicationStatus = Literal["pending", "approved", "rejected", "withdrawn"]


class OrderUserRef(BaseModel):
    """订单 / 申请 / 日志里展示的用户摘要（发布企业、接单工程师、申请人、审批人）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    certification: Certification | None


class WorkLogResponse(BaseModel):
    id: int
    order_id: int
    author: OrderUserRef
    content: str
    worked_hours: float | None
    created_at: datetime


class OrderResponse(BaseModel):
    """订单大厅列表项与详情共用的订单结构。"""

    id: int
    code: str
    title: str
    industry: str
    description: str
    delivery_days: int
    price_cents: int
    status: OrderStatus
    escrow_status: EscrowStatus
    publisher: OrderUserRef
    engineer: OrderUserRef | None
    work_log_count: int
    created_at: datetime
    updated_at: datetime
    claimed_at: datetime | None
    completed_at: datetime | None


class OrderDetailResponse(OrderResponse):
    """订单详情：在订单字段之外附带工作日志（按时间正序）。"""

    logs: list[WorkLogResponse]


class OrderListResponse(BaseModel):
    """分页信封，订单大厅 / 我发布的 / 我接到的共用。"""

    items: list[OrderResponse]
    total: int
    page: int
    page_size: int


class OrderCreateRequest(BaseModel):
    """发布需求。"""

    title: str = Field(min_length=1, max_length=120)
    industry: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=4000)
    delivery_days: int = Field(ge=1, le=365)
    price_cents: int = Field(ge=1, le=1_000_000_000)


class WorkLogCreateRequest(BaseModel):
    """工程师提交工作日志。"""

    content: str = Field(min_length=1, max_length=4000)
    worked_hours: float | None = Field(default=None, ge=0, le=24)


class OrderApplicationCreateRequest(BaseModel):
    """申请接单（accept）或申请交付（delivery）。"""

    type: ApplicationType
    message: str | None = Field(default=None, max_length=500)


class ApplicationReviewRequest(BaseModel):
    """审批申请时可选的审批意见（approve / reject 共用）。"""

    note: str | None = Field(default=None, max_length=500)


class OrderApplicationResponse(BaseModel):
    """申请项：附带订单最新状态与申请人 / 审批人摘要。"""

    id: int
    order: OrderResponse
    type: ApplicationType
    status: ApplicationStatus
    message: str | None
    review_note: str | None
    applicant: OrderUserRef
    reviewer: OrderUserRef | None
    reviewed_at: datetime | None
    created_at: datetime


class OrderApplicationListResponse(BaseModel):
    """申请分页信封，我的申请 / 收到的申请共用。"""

    items: list[OrderApplicationResponse]
    total: int
    page: int
    page_size: int


__all__ = [
    "ApplicationReviewRequest",
    "ApplicationStatus",
    "ApplicationType",
    "Certification",
    "EscrowStatus",
    "OrderApplicationCreateRequest",
    "OrderApplicationListResponse",
    "OrderApplicationResponse",
    "OrderCreateRequest",
    "OrderDetailResponse",
    "OrderListResponse",
    "OrderResponse",
    "OrderStatus",
    "OrderUserRef",
    "WorkLogCreateRequest",
    "WorkLogResponse",
]
