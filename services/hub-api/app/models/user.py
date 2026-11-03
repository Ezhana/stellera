"""用户表。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.rbac import Role


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 登录名与邮箱都唯一；登录使用 username（见 ADR 0001 / 前端登录页）。
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )

    # 只读角色视图：认证状态与响应映射可直接读 user.roles；
    # lazy="selectin" 让订单 / 申请里的用户摘要批量预加载，避免 N+1。
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="user_roles", lazy="selectin", viewonly=True
    )
