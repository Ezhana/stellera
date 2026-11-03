"""钱包与钱包流水。

金额单位统一为“分”。流水记录 balance_after_cents（该笔发生后的余额），
便于账实核对；钱包余额只能在流水写入的同一事务里变更。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin
from app.models.user import User


class Wallet(TimestampMixin, Base):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    balance_cents: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    user: Mapped[User] = relationship()
    transactions: Mapped[list[WalletTransaction]] = relationship(
        back_populates="wallet",
        order_by="(WalletTransaction.created_at, WalletTransaction.id)",
    )


class WalletTransaction(Base):
    """一条资金流水：recharge / redeem / order_payment / order_refund /
    order_settlement / adjustment。"""

    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # recharge / redeem / order_payment / order_refund / order_settlement / adjustment。
    type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # credit（入账）/ debit（出账）。
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    # 始终为正数；方向由 direction 表达。
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_after_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    # 业务来源（例如 fde_order + 订单 id），用于幂等与对账。
    reference_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    reference_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 流水不可变，只有创建时间，没有 updated_at。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    wallet: Mapped[Wallet] = relationship(back_populates="transactions")


__all__ = ["Wallet", "WalletTransaction"]
