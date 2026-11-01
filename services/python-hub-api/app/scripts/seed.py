"""种子数据脚本：幂等地写入角色、权限与管理员/演示账号。

用法（数据库表已由 Alembic 迁移创建后）：
    uv run python -m app.scripts.seed
入口脚本 scripts/entrypoint.sh 会在 `alembic upgrade head` 之后自动执行。

角色树：authenticated -> viewer -> operator -> admin。
- 所有登录用户都会被投影到 role:authenticated；
- viewer 只读；operator 可写；admin 拥有全部 API 权限（含 /api/v1/admin/*）。
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.db import create_engine, create_session_factory
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.security.passwords import hash_password

# (name, parent, description)
ROLE_DEFINITIONS: tuple[tuple[str, str | None, str], ...] = (
    ("authenticated", None, "所有已登录用户的基线角色"),
    ("viewer", "authenticated", "只读访问"),
    ("operator", "viewer", "运营写操作"),
    ("admin", "operator", "全部权限"),
)

# (role, object, action, description)
# 权限按模块路径收窄，避免 viewer 的只读通配把未来的 /api/v1/admin/* 一并放开。
PERMISSION_DEFINITIONS: tuple[tuple[str, str, str, str], ...] = (
    ("authenticated", "/api/v1/auth/me", "^GET$", "读取当前用户"),
    ("authenticated", "/api/v1/auth/logout", "^POST$", "登出并吊销 refresh token"),
    ("viewer", "/api/v1/wallet/*", "^GET$", "只读：钱包"),
    ("viewer", "/api/v1/orders", "^GET$", "只读：订单列表"),
    ("viewer", "/api/v1/orders/*", "^GET$", "只读：订单详情"),
    ("viewer", "/api/v1/plaza/*", "^GET$", "只读：广场"),
    ("operator", "/api/v1/orders", "^(POST|PATCH)$", "运营：创建/更新订单"),
    ("operator", "/api/v1/orders/*", "^(PATCH|PUT)$", "运营：更新订单"),
    ("operator", "/api/v1/plaza/*", "^(POST|PUT|PATCH)$", "运营：广场写操作"),
    ("admin", "/api/v1/*", "^(GET|POST|PUT|PATCH|DELETE)$", "全部业务 API 权限"),
)

DEMO_OPERATOR_USERNAME = "operator"
DEMO_VIEWER_USERNAME = "viewer"


@dataclass(frozen=True)
class SeedResult:
    created_users: tuple[str, ...]
    created_roles: tuple[str, ...]
    created_permissions: int


async def _seed_roles(session: AsyncSession, result_created: list[str]) -> dict[str, Role]:
    existing = {role.name: role for role in (await session.execute(select(Role))).scalars()}
    for name, _parent, description in ROLE_DEFINITIONS:
        if name in existing:
            continue
        role = Role(name=name, description=description)
        session.add(role)
        existing[name] = role
        result_created.append(name)
    await session.flush()

    # 角色树需要拿到自增 id 之后再回填 parent_id。
    for name, parent_name, _description in ROLE_DEFINITIONS:
        parent = existing.get(parent_name) if parent_name else None
        existing[name].parent_id = parent.id if parent else None
    await session.flush()
    return existing


async def _seed_permissions(session: AsyncSession, roles: dict[str, Role]) -> int:
    existing_permissions = {
        (permission.object, permission.action): permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    existing_links = {
        (link.role_id, link.permission_id)
        for link in (await session.execute(select(RolePermission))).scalars()
    }
    created = 0
    for role_name, object_pattern, action_pattern, description in PERMISSION_DEFINITIONS:
        role = roles[role_name]
        permission = existing_permissions.get((object_pattern, action_pattern))
        if permission is None:
            permission = Permission(
                object=object_pattern,
                action=action_pattern,
                description=description,
            )
            session.add(permission)
            await session.flush()
            existing_permissions[(object_pattern, action_pattern)] = permission
            created += 1
        if (role.id, permission.id) not in existing_links:
            session.add(RolePermission(role_id=role.id, permission_id=permission.id))
            existing_links.add((role.id, permission.id))
    return created


async def _ensure_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: Role,
    created: list[str],
) -> None:
    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        created.append(username)

    existing_link = (
        await session.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == role.id,
            )
        )
    ).scalar_one_or_none()
    if existing_link is None:
        session.add(UserRole(user_id=user.id, role_id=role.id))


async def seed_database(
    settings: Settings, session_factory: async_sessionmaker[AsyncSession]
) -> SeedResult:
    created_users: list[str] = []
    created_roles: list[str] = []
    async with session_factory() as session:
        roles = await _seed_roles(session, created_roles)
        created_permissions = await _seed_permissions(session, roles)

        await _ensure_user(
            session,
            username=settings.seed_admin_username.strip().lower(),
            email=settings.seed_admin_email.strip().lower(),
            password=settings.seed_admin_password,
            full_name="系统管理员",
            role=roles["admin"],
            created=created_users,
        )
        if settings.seed_demo_users:
            await _ensure_user(
                session,
                username=DEMO_OPERATOR_USERNAME,
                email=f"{DEMO_OPERATOR_USERNAME}@example.com",
                password=settings.seed_operator_password,
                full_name="运营（演示）",
                role=roles["operator"],
                created=created_users,
            )
            await _ensure_user(
                session,
                username=DEMO_VIEWER_USERNAME,
                email=f"{DEMO_VIEWER_USERNAME}@example.com",
                password=settings.seed_viewer_password,
                full_name="访客（演示）",
                role=roles["viewer"],
                created=created_users,
            )
        await session.commit()

    return SeedResult(
        created_users=tuple(created_users),
        created_roles=tuple(created_roles),
        created_permissions=created_permissions,
    )


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        result = await seed_database(settings, session_factory)
    finally:
        await engine.dispose()
    print(
        "seed done: "
        f"roles+{len(result.created_roles)} {list(result.created_roles)}, "
        f"permissions+{result.created_permissions}, "
        f"users+{len(result.created_users)} {list(result.created_users)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
