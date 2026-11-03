"""认证申请表：实名 / 企业 / 工程师三类认证共用一张表。

字段按类型取值（其余为 null），由服务层做必填与业务校验；审核通过后把结果
同步成 users.full_name 与 user_roles（realname / enterprise / engineer）。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.user import User


class CertificationApplication(Base):
    __tablename__ = "certification_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # realname / enterprise / engineer。
    type: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # pending / approved / rejected。
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)

    real_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    company_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credit_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    skills: Mapped[str | None] = mapped_column(String(255), nullable=True)
    work_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    project_experience: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    review_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 申请只记录创建时间，没有 updated_at。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # 两个外键都指向 users，必须显式声明 foreign_keys 避免歧义。
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    reviewer: Mapped[User | None] = relationship(foreign_keys=[reviewer_id])


__all__ = ["CertificationApplication"]
