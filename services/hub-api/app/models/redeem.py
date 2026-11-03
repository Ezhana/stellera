"""兑换码：线下充值渠道的一次性入账凭证。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.user import User


class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 对外展示的兑换码，格式 RDM-XXXX-XXXX-XXXX（大写、去易混字符）。
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # active / used / disabled。
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # 同一批生成的兑换码共用批次号，便于管理端按批次筛选。
    batch_no: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 两个外键都指向 users，必须显式声明 foreign_keys 避免歧义。
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id])
    used_by: Mapped[User | None] = relationship(foreign_keys=[used_by_id])


__all__ = ["RedeemCode"]
