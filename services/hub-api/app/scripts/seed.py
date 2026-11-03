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
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db import create_engine, create_session_factory
from app.models.base import ensure_utc, utcnow
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.redeem import RedeemCode
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction
from app.security.passwords import hash_password
from app.services.fde import (
    ESCROW_STATUS_HELD,
    ESCROW_STATUS_RELEASED,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_OPEN,
)
from app.services.system_settings import ensure_default_settings
from app.services.wallet import (
    DIRECTION_CREDIT,
    DIRECTION_DEBIT,
    REDEEM_STATUS_USED,
    REFERENCE_TYPE_FDE_ORDER,
    TRANSACTION_TYPE_ORDER_PAYMENT,
    TRANSACTION_TYPE_ORDER_SETTLEMENT,
    TRANSACTION_TYPE_RECHARGE,
    TRANSACTION_TYPE_REDEEM,
)

SEED_DATA_DIR = Path(__file__).resolve().parent / "seed_data"

# 演示金融事件的时间锚点（相对当前时间的固定偏移，保证重复执行结果稳定）。
DEMO_INITIAL_RECHARGE_DAYS = 120
DEMO_REDEEM_DAYS = 70
DEMO_REDEEM_BATCH_NO = "RDM-DEMO-2026"

# 已退役的角色：seed 每次都会把持有者迁移成 member 后删除角色行。
RETIRED_ROLE_NAMES: tuple[str, ...] = ("viewer", "operator")
MEMBER_ROLE = "member"

# 旧演示账号：仅用户名与邮箱同时精确匹配时才清理。
LEGACY_DEMO_USERS: tuple[tuple[str, str], ...] = (
    ("operator", "operator@example.com"),
    ("viewer", "viewer@example.com"),
)


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
class DemoWalletDefinition:
    username: str
    initial_balance_cents: int


@dataclass(frozen=True)
class DemoRedeemCodeDefinition:
    code: str
    amount_cents: int
    status: str
    note: str
    used_by_username: str | None = None


@dataclass(frozen=True)
class _WalletEvent:
    """种子脚本内部的金融事件，按时间排序后逐个应用以获得正确 balance_after。"""

    username: str
    created_at: datetime
    type: str
    direction: str
    amount_cents: int
    description: str
    reference_type: str | None = None
    reference_id: int | None = None


@dataclass(frozen=True)
class SeedResult:
    created_users: tuple[str, ...]
    created_roles: tuple[str, ...]
    created_permissions: int
    created_orders: int
    created_wallets: int
    created_wallet_transactions: int
    created_redeem_codes: int
    created_settings: int
    retired_roles: tuple[str, ...] = ()
    removed_users: tuple[str, ...] = ()


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
) -> tuple[
    tuple[DemoUserDefinition, ...],
    tuple[DemoOrderDefinition, ...],
    tuple[DemoWalletDefinition, ...],
    tuple[DemoRedeemCodeDefinition, ...],
]:
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
    wallets = tuple(
        DemoWalletDefinition(
            username=wallet["username"],
            initial_balance_cents=wallet["initial_balance_cents"],
        )
        for wallet in data.get("wallets", ())
    )
    redeem_codes = tuple(
        DemoRedeemCodeDefinition(
            code=code["code"],
            amount_cents=code["amount_cents"],
            status=code["status"],
            note=code["note"],
            used_by_username=code.get("used_by_username"),
        )
        for code in data.get("redeem_codes", ())
    )
    return users, orders, wallets, redeem_codes


async def _seed_roles(
    session: AsyncSession,
    definitions: tuple[RoleDefinition, ...],
    created: list[str],
) -> dict[str, Role]:
    existing = {role.name: role for role in (await session.execute(select(Role))).scalars()}
    for definition in definitions:
        role = existing.get(definition.name)
        if role is None:
            role = Role(name=definition.name)
            session.add(role)
            existing[definition.name] = role
            created.append(definition.name)
        # 已存在的角色也同步描述，保证 TOML 是唯一事实来源。
        role.description = definition.description
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
    """按 TOML 收敛权限与角色-权限关系：新增缺失行，同时清理已下线的旧策略。"""
    existing_permissions = {
        (permission.object, permission.action): permission
        for permission in (await session.execute(select(Permission))).scalars()
    }
    existing_links = {
        (link.role_id, link.permission_id)
        for link in (await session.execute(select(RolePermission))).scalars()
    }
    wanted_links: set[tuple[int, int]] = set()
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
        wanted_links.add((role.id, permission.id))

    stale_links = existing_links - wanted_links
    for role_id, permission_id in stale_links:
        await session.execute(
            delete(RolePermission).where(
                RolePermission.role_id == role_id,
                RolePermission.permission_id == permission_id,
            )
        )
    used_permission_ids = {permission_id for _, permission_id in wanted_links}
    orphan_permission_ids = [
        permission.id
        for permission in existing_permissions.values()
        if permission.id not in used_permission_ids
    ]
    if orphan_permission_ids:
        await session.execute(delete(Permission).where(Permission.id.in_(orphan_permission_ids)))

    for role_id, permission_id in wanted_links - existing_links:
        session.add(RolePermission(role_id=role_id, permission_id=permission_id))
    await session.flush()
    return created


async def _retire_roles(
    session: AsyncSession,
    roles: dict[str, Role],
) -> tuple[str, ...]:
    """退役历史角色：持有者补 member 角色后删除 user_roles / role_permissions / role 行。"""
    retired = (
        (await session.execute(select(Role).where(Role.name.in_(RETIRED_ROLE_NAMES))))
        .scalars()
        .all()
    )
    if not retired:
        return ()
    member_role = roles[MEMBER_ROLE]
    retired_ids = [role.id for role in retired]
    holder_ids = list(
        (
            await session.execute(select(UserRole.user_id).where(UserRole.role_id.in_(retired_ids)))
        ).scalars()
    )
    existing_member_ids = set(
        (
            await session.execute(
                select(UserRole.user_id).where(
                    UserRole.user_id.in_(holder_ids),
                    UserRole.role_id == member_role.id,
                )
            )
        ).scalars()
    )
    for user_id in holder_ids:
        if user_id not in existing_member_ids:
            session.add(UserRole(user_id=user_id, role_id=member_role.id))
    await session.execute(delete(UserRole).where(UserRole.role_id.in_(retired_ids)))
    await session.execute(delete(RolePermission).where(RolePermission.role_id.in_(retired_ids)))
    await session.execute(delete(Role).where(Role.id.in_(retired_ids)))
    await session.flush()
    return tuple(role.name for role in retired)


async def _migrate_legacy_demo_users(
    session: AsyncSession,
    *,
    member_user: User,
    member_role: Role,
) -> tuple[str, ...]:
    """清理旧演示账号：兑换码使用人转给 member；被订单引用的账号转为 member 保留。"""
    removed: list[str] = []
    for username, email in LEGACY_DEMO_USERS:
        user = (
            await session.execute(
                select(User).where(User.username == username, User.email == email)
            )
        ).scalar_one_or_none()
        if user is None:
            continue
        # 删除前把兑换码使用人改到 member，避免悬空引用或唯一约束失败。
        await session.execute(
            update(RedeemCode)
            .where(RedeemCode.used_by_id == user.id)
            .values(used_by_id=member_user.id)
        )
        referenced = (
            await session.execute(
                select(FdeOrder.id)
                .where(
                    or_(
                        FdeOrder.publisher_id == user.id,
                        FdeOrder.engineer_id == user.id,
                    )
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if referenced is None:
            # 工作日志作者同样有外键约束，被引用时也要保留账号。
            referenced = (
                await session.execute(
                    select(FdeOrderLog.author_id).where(FdeOrderLog.author_id == user.id).limit(1)
                )
            ).scalar_one_or_none()
        if referenced is not None:
            # 被订单 / 工作日志引用时不能删除：转为 member 账号保留（历史数据仍可展示）。
            existing = (
                await session.execute(
                    select(UserRole).where(
                        UserRole.user_id == user.id,
                        UserRole.role_id == member_role.id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(UserRole(user_id=user.id, role_id=member_role.id))
            continue
        # refresh_tokens / user_roles / wallets 由数据库外键 CASCADE 清理。
        await session.delete(user)
        removed.append(username)
    await session.flush()
    return tuple(removed)


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


async def _wallet_transaction_exists(
    session: AsyncSession, wallet_id: int, event: _WalletEvent
) -> bool:
    """按业务引用（订单）或描述（充值 / 兑换）判断事件是否已写入。"""
    filters = [
        WalletTransaction.wallet_id == wallet_id,
        WalletTransaction.type == event.type,
    ]
    if event.reference_type is not None:
        filters.extend(
            [
                WalletTransaction.reference_type == event.reference_type,
                WalletTransaction.reference_id == event.reference_id,
            ]
        )
    else:
        filters.append(WalletTransaction.description == event.description)
    row = (
        await session.execute(select(WalletTransaction.id).where(*filters).limit(1))
    ).scalar_one_or_none()
    return row is not None


async def _seed_demo_wallets(
    session: AsyncSession,
    definitions: tuple[DemoWalletDefinition, ...],
    order_definitions: tuple[DemoOrderDefinition, ...],
    redeem_definitions: tuple[DemoRedeemCodeDefinition, ...],
    users: dict[str, User],
) -> tuple[int, int]:
    """演示钱包与流水：初始充值 + 订单托管 / 结算 + 已用兑换码，按时间顺序应用。"""
    now = utcnow()
    created_wallets = 0
    wallets: dict[str, Wallet] = {}
    for definition in definitions:
        user = users[definition.username]
        wallet = (
            await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        ).scalar_one_or_none()
        if wallet is None:
            wallet = Wallet(user_id=user.id, balance_cents=0)
            session.add(wallet)
            created_wallets += 1
        wallets[definition.username] = wallet
    await session.flush()

    events: list[_WalletEvent] = []
    for definition in definitions:
        if definition.initial_balance_cents <= 0:
            continue
        events.append(
            _WalletEvent(
                username=definition.username,
                created_at=now - timedelta(days=DEMO_INITIAL_RECHARGE_DAYS),
                type=TRANSACTION_TYPE_RECHARGE,
                direction=DIRECTION_CREDIT,
                amount_cents=definition.initial_balance_cents,
                description="线下充值（演示）",
            )
        )

    orders = {
        order.code: order
        for order in (
            await session.execute(
                select(FdeOrder).where(
                    FdeOrder.code.in_([definition.code for definition in order_definitions])
                )
            )
        )
        .scalars()
        .all()
    }
    for definition in order_definitions:
        order = orders.get(definition.code)
        if order is None:
            continue
        events.append(
            _WalletEvent(
                username="enterprise",
                created_at=ensure_utc(order.created_at),
                type=TRANSACTION_TYPE_ORDER_PAYMENT,
                direction=DIRECTION_DEBIT,
                amount_cents=order.price_cents,
                description=f"发布订单 {order.code} 托管",
                reference_type=REFERENCE_TYPE_FDE_ORDER,
                reference_id=order.id,
            )
        )
        if order.status == ORDER_STATUS_COMPLETED and order.completed_at is not None:
            events.append(
                _WalletEvent(
                    username="engineer",
                    created_at=ensure_utc(order.completed_at),
                    type=TRANSACTION_TYPE_ORDER_SETTLEMENT,
                    direction=DIRECTION_CREDIT,
                    amount_cents=order.price_cents,
                    description=f"订单 {order.code} 结算",
                    reference_type=REFERENCE_TYPE_FDE_ORDER,
                    reference_id=order.id,
                )
            )

    for definition in redeem_definitions:
        if definition.status != REDEEM_STATUS_USED or definition.used_by_username is None:
            continue
        events.append(
            _WalletEvent(
                username=definition.used_by_username,
                created_at=now - timedelta(days=DEMO_REDEEM_DAYS),
                type=TRANSACTION_TYPE_REDEEM,
                direction=DIRECTION_CREDIT,
                amount_cents=definition.amount_cents,
                description=f"兑换码 {definition.code} 入账",
            )
        )

    events.sort(key=lambda event: event.created_at)
    created_transactions = 0
    for event in events:
        wallet = wallets[event.username]
        if await _wallet_transaction_exists(session, wallet.id, event):
            continue
        if event.direction == DIRECTION_CREDIT:
            wallet.balance_cents += event.amount_cents
        else:
            wallet.balance_cents -= event.amount_cents
        session.add(
            WalletTransaction(
                wallet_id=wallet.id,
                type=event.type,
                direction=event.direction,
                amount_cents=event.amount_cents,
                balance_after_cents=wallet.balance_cents,
                description=event.description,
                reference_type=event.reference_type,
                reference_id=event.reference_id,
                created_at=event.created_at,
            )
        )
        created_transactions += 1
    return created_wallets, created_transactions


async def _seed_demo_redeem_codes(
    session: AsyncSession,
    definitions: tuple[DemoRedeemCodeDefinition, ...],
    users: dict[str, User],
) -> int:
    """兑换码只在 code 不存在时插入；used 的同时写入使用人。"""
    existing_codes = set(
        (
            await session.execute(
                select(RedeemCode.code).where(
                    RedeemCode.code.in_([definition.code for definition in definitions])
                )
            )
        ).scalars()
    )
    now = utcnow()
    created = 0
    for definition in definitions:
        if definition.code in existing_codes:
            continue
        used_by = users.get(definition.used_by_username) if definition.used_by_username else None
        session.add(
            RedeemCode(
                code=definition.code,
                amount_cents=definition.amount_cents,
                status=definition.status,
                batch_no=DEMO_REDEEM_BATCH_NO,
                note=definition.note,
                created_by_id=None,
                used_by_id=used_by.id if used_by is not None else None,
                used_at=(
                    now - timedelta(days=DEMO_REDEEM_DAYS)
                    if definition.status == REDEEM_STATUS_USED
                    else None
                ),
                expires_at=None,
                created_at=now - timedelta(days=DEMO_INITIAL_RECHARGE_DAYS),
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
    if demo:
        (
            demo_user_definitions,
            demo_order_definitions,
            demo_wallet_definitions,
            demo_redeem_definitions,
        ) = load_demo()
    else:
        demo_user_definitions, demo_order_definitions = (), ()
        demo_wallet_definitions, demo_redeem_definitions = (), ()

    created_users: list[str] = []
    created_roles: list[str] = []
    async with session_factory() as session:
        roles = await _seed_roles(session, role_definitions, created_roles)
        created_permissions = await _seed_permissions(session, permission_definitions, roles)
        # 退役 viewer / operator：先把持有者迁到 member，再删角色与关联行。
        retired_roles = await _retire_roles(session, roles)

        admin_user = await _ensure_user(
            session,
            username=settings.admin_username.strip().lower(),
            email=settings.admin_email.strip().lower(),
            password=settings.admin_password,
            full_name="系统管理员",
            role=roles["admin"],
            created=created_users,
        )

        created_orders = 0
        created_wallets = 0
        created_wallet_transactions = 0
        created_redeem_codes = 0
        removed_users: tuple[str, ...] = ()
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
            # 旧演示账号（operator / viewer）在 member 账号就绪后清理。
            removed_users = await _migrate_legacy_demo_users(
                session,
                member_user=demo_users[MEMBER_ROLE],
                member_role=roles[MEMBER_ROLE],
            )
            # 演示订单必须在演示用户（发布方/工程师）存在之后写入。
            created_orders = await _seed_demo_orders(
                session,
                demo_order_definitions,
                demo_users["enterprise"],
                demo_users["engineer"],
            )
            # 钱包流水依赖演示订单（含创建时间与金额），同一 session 内可见。
            # 管理员用户名可被环境变量改写，demo.toml 里统一用 admin 占位。
            demo_users[admin_user.username] = admin_user
            demo_users.setdefault("admin", admin_user)
            created_wallets, created_wallet_transactions = await _seed_demo_wallets(
                session,
                demo_wallet_definitions,
                demo_order_definitions,
                demo_redeem_definitions,
                demo_users,
            )
            created_redeem_codes = await _seed_demo_redeem_codes(
                session, demo_redeem_definitions, demo_users
            )
        # 系统设置始终应用（demo=False 也写默认值），只插入缺失行、不覆盖已有修改。
        created_settings = await ensure_default_settings(session)
        await session.commit()

    return SeedResult(
        created_users=tuple(created_users),
        created_roles=tuple(created_roles),
        created_permissions=created_permissions,
        created_orders=created_orders,
        created_wallets=created_wallets,
        created_wallet_transactions=created_wallet_transactions,
        created_redeem_codes=created_redeem_codes,
        created_settings=created_settings,
        retired_roles=retired_roles,
        removed_users=removed_users,
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
        f"fde_orders+{result.created_orders}, "
        f"wallets+{result.created_wallets}, "
        f"wallet_transactions+{result.created_wallet_transactions}, "
        f"redeem_codes+{result.created_redeem_codes}, "
        f"settings+{result.created_settings}, "
        f"retired_roles={list(result.retired_roles)}, "
        f"removed_users={list(result.removed_users)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="写入 RBAC、管理员账号与（可选）演示数据")
    parser.add_argument(
        "--demo", action="store_true", help="同时写入演示账号、FDE 订单、钱包与兑换码"
    )
    args = parser.parse_args()
    run_seed(demo=args.demo)


if __name__ == "__main__":
    main()
