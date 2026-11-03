"""FDE 订单、工作日志与申请审批表。

订单状态机（发布者审批申请驱动）：
    open --申请接单 + 发布者通过--> in_progress --申请交付 + 发布者通过--> completed
    open --发布者取消--> cancelled
托管资金随订单流转：初始 held（平台代收），完成审批后 released（放款给工程师），
取消后 refunded（退回企业）。申请记录保留审批人与审批意见，便于追溯。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base, TimestampMixin
from app.models.user import User


class FdeOrder(TimestampMixin, Base):
    """企业发布的 FDE 需求订单（平台代收并托管资金）。"""

    __tablename__ = "fde_orders"
    __table_args__ = (
        # 订单大厅按发布时间倒序分页，单独建索引避免排序走全表扫描。
        Index("ix_fde_orders_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 对前端稳定可见的业务单号，例如 FDE-2026-0001；演示数据用 FDE-DEMO-0001。
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    industry: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # 以“分”为单位存整数，避免浮点金额误差；上限 10 亿分（1000 万元）。
    price_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    # open / in_progress / completed / cancelled，见模块 docstring 的状态机。
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # held / released / refunded。
    escrow_status: Mapped[str] = mapped_column(String(16), nullable=False)
    publisher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    engineer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 两个外键都指向 users，必须显式声明 foreign_keys 避免歧义。
    publisher: Mapped[User] = relationship(foreign_keys=[publisher_id])
    engineer: Mapped[User | None] = relationship(foreign_keys=[engineer_id])
    logs: Mapped[list[FdeOrderLog]] = relationship(
        back_populates="order",
        order_by="(FdeOrderLog.created_at, FdeOrderLog.id)",
    )
    applications: Mapped[list[FdeOrderApplication]] = relationship(
        back_populates="order",
        order_by="(FdeOrderApplication.created_at, FdeOrderApplication.id)",
    )


class FdeOrderLog(Base):
    """工程师在订单进行中提交的工作日志。"""

    __tablename__ = "fde_order_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("fde_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 本次投入工时（小时），可为空；上限 24 由 Pydantic schema 校验。
    worked_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    # 日志只记录创建时间，没有 updated_at，所以不复用 TimestampMixin。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[FdeOrder] = relationship(back_populates="logs")
    author: Mapped[User] = relationship()


class FdeOrderApplication(Base):
    """接单 / 交付申请：由发布者审批后驱动订单状态流转。"""

    __tablename__ = "fde_order_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("fde_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    applicant_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    # accept（申请接单）/ delivery（申请交付）。
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # pending / approved / rejected / withdrawn。
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 申请只记录创建时间，没有 updated_at。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order: Mapped[FdeOrder] = relationship(back_populates="applications")
    applicant: Mapped[User] = relationship(foreign_keys=[applicant_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])


__all__ = ["FdeOrder", "FdeOrderApplication", "FdeOrderLog"]
