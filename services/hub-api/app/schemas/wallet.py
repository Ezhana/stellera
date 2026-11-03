"""钱包相关请求/响应模型。

字段与前端 BFF 契约一一对应；时间统一由端点转成 UTC 后序列化。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TransactionType = Literal[
    "recharge",
    "redeem",
    "order_payment",
    "order_refund",
    "order_settlement",
]
TransactionDirection = Literal["credit", "debit"]


class WalletTransactionResponse(BaseModel):
    """一条钱包流水。"""

    id: int
    type: TransactionType
    direction: TransactionDirection
    amount_cents: int
    balance_after_cents: int
    description: str
    reference_type: str | None
    reference_id: int | None
    created_at: datetime


class WalletSummaryResponse(BaseModel):
    """钱包首页汇总。"""

    balance_cents: int
    usage_total_cents: int
    recharge_total_cents: int
    redeem_total_cents: int
    income_total_cents: int
    # 在线充值永久关闭，前端据此只展示兑换码入口。
    recharge_enabled: bool
    recharge_note: str
    support_contact: str


class WalletTransactionListResponse(BaseModel):
    """流水分页信封。"""

    items: list[WalletTransactionResponse]
    total: int
    page: int
    page_size: int


class RedeemRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class RedeemResponse(BaseModel):
    """兑换结果：入账金额、兑换后余额与本次流水。"""

    amount_cents: int
    balance_cents: int
    transaction: WalletTransactionResponse


__all__ = [
    "RedeemRequest",
    "RedeemResponse",
    "TransactionDirection",
    "TransactionType",
    "WalletSummaryResponse",
    "WalletTransactionListResponse",
    "WalletTransactionResponse",
]
