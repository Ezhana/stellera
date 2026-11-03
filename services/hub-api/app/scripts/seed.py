"""种子数据：从 TOML fixture 幂等写入 RBAC、管理员与（可选）演示数据。

用法：
    python -m app.scripts.init [--demo]   # 初始化 job：先迁移再写种子
    python -m app.scripts.seed [--demo]   # 只写种子
"""

from __future__ import annotations

import argparse
import asyncio
import tomllib
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db import create_engine, create_session_factory
from app.models.base import utcnow
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.user import User
from app.security.passwords import hash_password
from app.services.fde import (
    ESCROW_STATUS_HELD,
    ESCROW_STATUS_RELEASED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_OPEN,
)

SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"


class SeedSettings(BaseSettings):
    """初始化 job 的环境变量；不进入 `app.core.config.Settings`。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    admin_username: str = "admin"
    admin_email: str = "admin@example.com"
    admin_password: str = "admin12345"


@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str
    parent: str | None = None


@dataclass(frozen=True)
class PermissionDefinition:
    role: str
    object: str
    action: str
    description: str


@dataclass(frozen=True)
class DemoUserDefinition:
    username: str
    email: str
    password: str
    full_name: str
    role: str


@dataclass(frozen=True)
class DemoWorkLogDefinition:
    content: str
    worked_hours: float | None
    days_ago: int


@dataclass(frozen=True)
class DemoOrderDefinition:
    code: str
    title: str
    industry: str
    description: str
    delivery_days: int
    price_cents: int
    status: str
    created_days_ago: int
    claimed_days_ago: int | None = None
    completed_days_ago: int | None = None
    logs: tuple[DemoWorkLogDefinition, ...] = ()


@dataclass(frozen=True)
class SeedResult:
    created_users: tuple[str, ...]
    created_roles: tuple[str, ...]
    created_permissions: int
    created_orders: int


def _read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as file:
        return tomllib.load(file)


def load_rbac(
    path: Path = SEED_DATA_DIR / "rbac.toml",
) -> tuple[tuple[RoleDefinition, ...], tuple[PermissionDefinition, ...]]:
    data = _read_toml(path)
    roles = tuple(
        RoleDefinition(
            name=role["name"],
            description=role["description"],
            parent=role.get("parent"),
        )
        for role in data["roles"]
    )
    permissions = tuple(
        PermissionDefinition(
            role=permission["role"],
            object=permission["object"],
            action=permission["action"],
            description=permission["description"],
        )
        for permission in data["permissions"]
    )
    return roles, permissions


def load_demo(
    path: Path = SEED_DATA_DIR / "demo.toml",
) -> tuple[tuple[DemoUserDefinition, ...], tuple[DemoOrderDefinition, ...]]:
    data = _read_toml(path)
    users = tuple(
        DemoUserDefinition(
            username=user["username"],
            email=user["email"],
            password=user["password"],
            full_name=user["full_name"],
            role=user["role"],
        )
        for user in data["users"]
    )
    orders = tuple(
        DemoOrderDefinition(
            code=order["code"],
            title=order["title"],
            industry=order["industry"],
            description=order["description"],
            delivery_days=order["delivery_days"],
            price_cents=order["price_cents"],
            status=order["status"],
            created_days_ago=order["created_days_ago"],
            claimed_days_ago=order.get("claimed_days_ago"),
            completed_days_ago=order.get("completed_days_ago"),
            logs=tuple(
                DemoWorkLogDefinition(
                    content=log["content"],
                    worked_hours=log.get("worked_hours"),
                    days_ago=log["days_ago"],
                )
                for log in order.get("logs", ())
            ),
        )
        for order in data["orders"]
    )
    return users, orders


async def _seed_roles(
    session: AsyncSession,
    definitions: tuple[RoleDefinition, ...],
    created: list[str],
) -> dict[str, Role]:
    existing = {role.name: role for role in (await session.execute(select(Role))).scalars()}
    for definition in definitions:
        if definition.name in existing:
            continue
        role = Role(name=definition.name, description=definition.description)
        session.add(role)
        existing[definition.name] = role
        created.append(definition.name)
    await session.flush()

    # 角色树需要拿到自增 id 之后再回填 parent_id。
    for definition in definitions:
        parent = existing.get(definition.parent) if definition.parent else None
        existing[definition.name].parent_id = parent.id if parent else None
    await session.flush()
    return existing


async def _seed_permissions(
    session: AsyncSession,
    definitions: tuple[PermissionDefinition, ...],
    roles: dict[str, Role],
) -> int:
    existing_permissions = {
        (permission.object, permission.action): permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    existing_links = {
        (link.role_id, link.permission_id)
        for link in (await session.execute(select(RolePermission))).scalars()
    }
    created = 0
    for definition in definitions:
        role = roles[definition.role]
        permission = existing_permissions.get((definition.object, definition.action))
        if permission is None:
            permission = Permission(
                object=definition.object,
                action=definition.action,
                description=definition.description,
            )
            session.add(permission)
            await session.flush()
            existing_permissions[(definition.object, definition.action)] = permission
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
) -> User:
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
    return user


async def _seed_demo_orders(
    session: AsyncSession,
    definitions: tuple[DemoOrderDefinition, ...],
    publisher: User,
    engineer: User,
) -> int:
    """写入演示订单；单号已存在则跳过，保证可重复执行。"""
    existing_codes = set(
        (
            await session.execute(
                select(FdeOrder.code).where(
                    FdeOrder.code.in_([definition.code for definition in definitions])
                )
            )
        ).scalars()
    )
    now = utcnow()
    created = 0
    for definition in definitions:
        if definition.code in existing_codes:
            continue
        created_at = now - timedelta(days=definition.created_days_ago)
        claimed_at = (
            now - timedelta(days=definition.claimed_days_ago)
            if definition.claimed_days_ago is not None
            else None
        )
        completed_at = (
            now - timedelta(days=definition.completed_days_ago)
            if definition.completed_days_ago is not None
            else None
        )
        order = FdeOrder(
            code=definition.code,
            title=definition.title,
            industry=definition.industry,
            description=definition.description,
            delivery_days=definition.delivery_days,
            price_cents=definition.price_cents,
            status=definition.status,
            escrow_status=(
                ESCROW_STATUS_RELEASED
                if definition.status == ORDER_STATUS_COMPLETED
                else ESCROW_STATUS_HELD
            ),
            publisher_id=publisher.id,
            engineer_id=engineer.id if definition.status != ORDER_STATUS_OPEN else None,
            claimed_at=claimed_at,
            completed_at=completed_at,
            created_at=created_at,
            updated_at=completed_at or claimed_at or created_at,
        )
        session.add(order)
        # 日志需要 order.id，先 flush 拿到自增主键。
        await session.flush()
        for log_definition in definition.logs:
            session.add(
                FdeOrderLog(
                    order_id=order.id,
                    author_id=engineer.id,
                    content=log_definition.content,
                    worked_hours=log_definition.worked_hours,
                    created_at=now - timedelta(days=log_definition.days_ago),
                )
            )
        created += 1
    return created


async def seed_database(
    settings: SeedSettings,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    demo: bool = False,
) -> SeedResult:
    role_definitions, permission_definitions = load_rbac()
    demo_user_definitions, demo_order_definitions = load_demo() if demo else ((), ())

    created_users: list[str] = []
    created_roles: list[str] = []
    async with session_factory() as session:
        roles = await _seed_roles(session, role_definitions, created_roles)
        created_permissions = await _seed_permissions(session, permission_definitions, roles)

        await _ensure_user(
            session,
            username=settings.admin_username.strip().lower(),
            email=settings.admin_email.strip().lower(),
            password=settings.admin_password,
            full_name="系统管理员",
            role=roles["admin"],
            created=created_users,
        )

        created_orders = 0
        if demo_user_definitions:
            demo_users = {
                definition.username: await _ensure_user(
                    session,
                    username=definition.username,
                    email=definition.email,
                    password=definition.password,
                    full_name=definition.full_name,
                    role=roles[definition.role],
                    created=created_users,
                )
                for definition in demo_user_definitions
            }
            # 演示订单必须在演示用户（发布方/工程师）存在之后写入。
            created_orders = await _seed_demo_orders(
                session,
                demo_order_definitions,
                demo_users["enterprise"],
                demo_users["engineer"],
            )
        await session.commit()

    return SeedResult(
        created_users=tuple(created_users),
        created_roles=tuple(created_roles),
        created_permissions=created_permissions,
        created_orders=created_orders,
    )


async def _run(demo: bool) -> SeedResult:
    settings = SeedSettings()
    engine = create_engine(get_settings())
    session_factory = create_session_factory(engine)
    try:
        return await seed_database(settings, session_factory, demo=demo)
    finally:
        await engine.dispose()


def run_seed(*, demo: bool = False) -> None:
    result = asyncio.run(_run(demo))
    print(
        "seed done: "
        f"roles+{len(result.created_roles)} {list(result.created_roles)}, "
        f"permissions+{result.created_permissions}, "
        f"users+{len(result.created_users)} {list(result.created_users)}, "
        f"fde_orders+{result.created_orders}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="写入 RBAC 与管理员账号")
    parser.add_argument("--demo", action="store_true", help="同时写入演示账号与 FDE 演示订单")
    args = parser.parse_args()
    run_seed(demo=args.demo)


if __name__ == "__main__":
    main()
