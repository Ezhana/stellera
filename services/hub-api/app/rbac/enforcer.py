"""把 PostgreSQL 中的 RBAC 数据投影成 Casbin 内存策略。

投影规则（与 ADR 0001 一致）：
- 角色权限：`p, role:<name>, <object>, <action>`；
- 角色继承：`g, role:<child>, role:<parent>`；
- 用户角色：`g, user:<id>, role:<name>`；
- 所有用户额外加入 `role:authenticated`，保证登录后至少能访问 /auth/me 与 /auth/logout。

policy 不落 CSV 文件；每次进程启动从数据库重新加载。角色变更在下次登录/重启后
生效（管理端调整认证状态时会立即 resync 该用户）。
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import casbin
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.rbac.policies import PUBLIC_POLICIES

AUTHENTICATED_ROLE = "authenticated"
ANONYMOUS_SUBJECT = "anonymous"


def user_subject(user_id: int) -> str:
    return f"user:{user_id}"


def role_subject(role_name: str) -> str:
    return f"role:{role_name}"


@dataclass(frozen=True)
class RBACSnapshot:
    """一次从数据库读出的 RBAC 全量快照。"""

    role_parents: tuple[tuple[str, str], ...]
    role_permissions: tuple[tuple[str, str, str], ...]
    user_role_names: tuple[tuple[int, str], ...]
    user_ids: tuple[int, ...]


async def load_rbac_snapshot(session: AsyncSession) -> RBACSnapshot:
    role_rows = (await session.execute(select(Role.id, Role.name, Role.parent_id))).all()
    role_name_by_id = {row.id: row.name for row in role_rows}
    role_parents = tuple(
        (row.name, role_name_by_id[row.parent_id])
        for row in role_rows
        if row.parent_id is not None and row.parent_id in role_name_by_id
    )

    permission_rows = (
        await session.execute(
            select(Role.name, Permission.object, Permission.action)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .join(Permission, Permission.id == RolePermission.permission_id)
        )
    ).all()
    role_permissions = tuple((row.name, row.object, row.action) for row in permission_rows)

    user_role_rows = (
        await session.execute(
            select(UserRole.user_id, Role.name).join(Role, Role.id == UserRole.role_id)
        )
    ).all()
    user_role_names = tuple((row.user_id, row.name) for row in user_role_rows)

    user_ids = tuple((await session.execute(select(User.id))).scalars().all())

    return RBACSnapshot(
        role_parents=role_parents,
        role_permissions=role_permissions,
        user_role_names=user_role_names,
        user_ids=user_ids,
    )


async def load_user_role_names(session: AsyncSession, user_id: int) -> tuple[str, ...]:
    rows = (
        await session.execute(
            select(Role.name)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
    ).scalars()
    return tuple(rows.all())


def build_enforcer(model_path: Path | str, snapshot: RBACSnapshot) -> casbin.Enforcer:
    """构建并填充进程内 enforcer（不读 CSV adapter）。"""
    enforcer = casbin.Enforcer(str(model_path))

    for role_name, obj, action in snapshot.role_permissions:
        enforcer.add_policy(role_subject(role_name), obj, action)

    for subject, obj, action in PUBLIC_POLICIES:
        enforcer.add_policy(subject, obj, action)

    for child, parent in snapshot.role_parents:
        enforcer.add_grouping_policy(role_subject(child), role_subject(parent))

    for user_id, role_name in snapshot.user_role_names:
        enforcer.add_grouping_policy(user_subject(user_id), role_subject(role_name))

    for user_id in snapshot.user_ids:
        enforcer.add_grouping_policy(user_subject(user_id), role_subject(AUTHENTICATED_ROLE))

    enforcer.build_role_links()
    return enforcer


def resync_user_groupings(
    enforcer: casbin.Enforcer,
    user_id: int,
    role_names: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    """在登录时刷新单个用户的角色投影，返回最终生效的角色名（含 authenticated）。"""
    subject = user_subject(user_id)
    for grouping in enforcer.get_grouping_policy():
        if grouping and grouping[0] == subject:
            enforcer.remove_grouping_policy(*grouping)

    effective_roles = tuple(sorted({*role_names, AUTHENTICATED_ROLE}))
    for role_name in effective_roles:
        enforcer.add_grouping_policy(subject, role_subject(role_name))
    enforcer.build_role_links()
    return effective_roles


class EnforcerGuard:
    """包装 enforcer 的并发访问：Casbin 的 role manager 不是线程安全的。

    Starlette/TestClient 可能在不同线程处理请求，而登录时的投影写与请求时的
    enforce 读必须串行，否则 role link 构建过程中会读到半成品。
    """

    def __init__(self, enforcer: casbin.Enforcer) -> None:
        self._enforcer = enforcer
        self._lock = threading.Lock()

    @property
    def enforcer(self) -> casbin.Enforcer:
        return self._enforcer

    def enforce(self, subject: str, obj: str, action: str) -> bool:
        with self._lock:
            return bool(self._enforcer.enforce(subject, obj, action))

    def resync_user(self, user_id: int, role_names: tuple[str, ...] | list[str]) -> tuple[str, ...]:
        with self._lock:
            return resync_user_groupings(self._enforcer, user_id, role_names)

    def implicit_permissions_for_user(self, user_id: int) -> tuple[tuple[str, str], ...]:
        """用户经角色继承后的全部 (object, action)，按 object/action 去重排序。"""
        with self._lock:
            rules = self._enforcer.get_implicit_permissions_for_user(user_subject(user_id))
        grants = {(rule[1], rule[2]) for rule in rules if len(rule) >= 3}
        return tuple(sorted(grants))
