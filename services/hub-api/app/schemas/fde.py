"""FDE 订单相关请求/响应模型。

字段与前端 BFF 契约一一对应；时间统一由服务层转成 UTC 后序列化。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OrderStatus = Literal["open", "in_progress", "completed", "cancelled"]
EscrowStatus = Literal["held", "released", "refunded"]


class OrderUserRef(BaseModel):
    """订单里展示的用户摘要（发布企业 / 接单工程师）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str


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
    """分页信封，订单大厅与“我发布的”共用。"""

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


__all__ = [
    "EscrowStatus",
    "OrderCreateRequest",
    "OrderDetailResponse",
    "OrderListResponse",
    "OrderResponse",
    "OrderStatus",
    "OrderUserRef",
    "WorkLogCreateRequest",
    "WorkLogResponse",
]
