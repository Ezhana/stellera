"""刷新令牌：只存 SHA-256 摘要，支持旋转与重放吊销。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.models.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    # jti 是 refresh JWT 的 ID，作为主键便于按令牌精确吊销。
    jti: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # 轮换链：标记本行被哪个新 jti 替换（审计用，可为空）。
    replaced_by_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)


__all__ = ["RefreshToken"]
