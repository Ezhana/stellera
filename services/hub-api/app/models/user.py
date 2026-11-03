"""用户表。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, true
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
    # 昵称是展示名，注册时自动生成、用户可改；为空时回退 full_name / username。
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # full_name 只作实名：不可由个人资料或管理端编辑，只由实名认证审核通过时写入。
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 技能标签，逗号分隔；用逗号而非 JSON，便于前端直接展示与简单搜索。
    skills: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_wechat: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=true(), nullable=False
    )

    # 只读角色视图：认证状态与响应映射可直接读 user.roles；
    # lazy="selectin" 让订单 / 申请里的用户摘要批量预加载，避免 N+1。
    roles: Mapped[list[Role]] = relationship(
        "Role", secondary="user_roles", lazy="selectin", viewonly=True
    )
