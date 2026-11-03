"""种子脚本的幂等性、角色树、演示数据与旧角色 / 旧演示账号清理。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db import create_all_tables, create_engine, create_session_factory
from app.models.base import utcnow
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.models.redeem import RedeemCode
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction
from app.scripts.seed import load_demo, load_rbac, seed_database
from app.security.passwords import hash_password
from tests.conftest import build_seed_settings, build_test_settings

ROLE_DEFINITIONS, PERMISSION_DEFINITIONS = load_rbac()
(
    DEMO_USER_DEFINITIONS,
    DEMO_ORDER_DEFINITIONS,
    DEMO_WALLET_DEFINITIONS,
    DEMO_REDEEM_CODE_DEFINITIONS,
) = load_demo()

EXPECTED_DEMO_BALANCES = {
    "admin": 300_000_000,
    "member": 150_000,
    "enterprise": 212_300_000,
    "engineer": 15_700_000,
}


def _run_seed(settings: Settings, *, demo: bool = True) -> tuple[Any, Any, dict[str, Any]]:
    async def _run() -> tuple[Any, Any, dict[str, Any]]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            seed_settings = build_seed_settings()
            first = await seed_database(seed_settings, factory, demo=demo)
            second = await seed_database(seed_settings, factory, demo=demo)
            async with factory() as session:
                counts: dict[str, Any] = {
                    "users": (
                        await session.execute(select(func.count()).select_from(User))
                    ).scalar_one(),
                    "roles": (
                        await session.execute(select(func.count()).select_from(Role))
                    ).scalar_one(),
                    "permissions": (
                        await session.execute(select(func.count()).select_from(Permission))
                    ).scalar_one(),
                    "role_permissions": (
                        await session.execute(select(func.count()).select_from(RolePermission))
                    ).scalar_one(),
                    "links": (
                        await session.execute(select(func.count()).select_from(UserRole))
                    ).scalar_one(),
                    "orders": (
                        await session.execute(select(func.count()).select_from(FdeOrder))
                    ).scalar_one(),
                    "logs": (
                        await session.execute(select(func.count()).select_from(FdeOrderLog))
                    ).scalar_one(),
                    "wallets": (
                        await session.execute(select(func.count()).select_from(Wallet))
                    ).scalar_one(),
                    "wallet_transactions": (
                        await session.execute(select(func.count()).select_from(WalletTransaction))
                    ).scalar_one(),
                    "redeem_codes": (
                        await session.execute(select(func.count()).select_from(RedeemCode))
                    ).scalar_one(),
                    "settings": (
                        await session.execute(select(func.count()).select_from(SystemSetting))
                    ).scalar_one(),
                }
                balance_rows = (
                    await session.execute(
                        select(User.username, Wallet.balance_cents).join(
                            Wallet, Wallet.user_id == User.id
                        )
                    )
                ).all()
                counts["balances"] = {
                    username: balance_cents for username, balance_cents in balance_rows
                }
            return first, second, counts
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def test_seed_is_idempotent(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")

    first, second, counts = _run_seed(settings)

    assert first.created_users == ("admin", *[user.username for user in DEMO_USER_DEFINITIONS])
    assert first.created_users == ("admin", "member", "enterprise", "engineer")
    assert len(first.created_roles) == len(ROLE_DEFINITIONS) == 5
    assert first.created_permissions == len(PERMISSION_DEFINITIONS) == 17
    assert first.created_orders == len(DEMO_ORDER_DEFINITIONS) == 10
    assert first.created_wallets == len(DEMO_WALLET_DEFINITIONS) == 4
    # 3 条演示充值 + 10 条订单托管 + 2 条完成结算 + 1 条已用兑换码入账。
    assert first.created_wallet_transactions == 16
    assert first.created_redeem_codes == len(DEMO_REDEEM_CODE_DEFINITIONS) == 3
    assert first.created_settings == 3
    assert first.retired_roles == ()
    assert first.removed_users == ()

    # 第二次执行不应重复创建任何东西（含演示钱包、流水、兑换码与系统设置）。
    assert second.created_users == ()
    assert second.created_roles == ()
    assert second.created_permissions == 0
    assert second.created_orders == 0
    assert second.created_wallets == 0
    assert second.created_wallet_transactions == 0
    assert second.created_redeem_codes == 0
    assert second.created_settings == 0

    assert counts["users"] == 1 + len(DEMO_USER_DEFINITIONS) == 4
    assert counts["roles"] == 5
    assert counts["permissions"] == 17
    assert counts["links"] == 4
    assert counts["orders"] == 10
    assert counts["logs"] == 11
    assert counts["wallets"] == 4
    assert counts["wallet_transactions"] == 16
    assert counts["redeem_codes"] == 3
    assert counts["settings"] == 3
    assert counts["balances"] == EXPECTED_DEMO_BALANCES


def test_seed_without_demo_only_creates_admin(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed-nodemo.db'}")

    first, second, counts = _run_seed(settings, demo=False)

    assert first.created_users == ("admin",)
    assert first.created_roles == tuple(role.name for role in ROLE_DEFINITIONS)
    assert first.created_permissions == 17
    assert first.created_orders == 0
    assert first.created_wallets == 0
    assert first.created_wallet_transactions == 0
    assert first.created_redeem_codes == 0
    # 系统设置即使没有演示数据也会写入默认值。
    assert first.created_settings == 3
    assert second.created_settings == 0
    assert counts["users"] == 1
    assert counts["roles"] == 5
    assert counts["permissions"] == 17
    assert counts["links"] == 1
    assert counts["orders"] == 0
    assert counts["logs"] == 0
    assert counts["wallets"] == 0
    assert counts["wallet_transactions"] == 0
    assert counts["redeem_codes"] == 0
    assert counts["settings"] == 3


def test_role_tree_is_member_centered(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'roles.db'}")

    async def _load() -> dict[str, str | None]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            await seed_database(build_seed_settings(), factory, demo=True)
            async with factory() as session:
                rows = (await session.execute(select(Role))).scalars().all()
                by_id = {role.id: role.name for role in rows}
                return {
                    role.name: (by_id[role.parent_id] if role.parent_id else None) for role in rows
                }
        finally:
            await engine.dispose()

    parents = asyncio.run(_load())

    assert parents == {
        "authenticated": None,
        "member": "authenticated",
        "enterprise": "member",
        "engineer": "member",
        "admin": "member",
    }


def test_seed_permissions_match_rbac_toml(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'perms.db'}")

    async def _load() -> set[tuple[str, str, str]]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            await seed_database(build_seed_settings(), factory, demo=True)
            async with factory() as session:
                rows = (
                    await session.execute(
                        select(Role.name, Permission.object, Permission.action)
                        .join(RolePermission, RolePermission.role_id == Role.id)
                        .join(Permission, Permission.id == RolePermission.permission_id)
                    )
                ).all()
                return {(row[0], row[1], row[2]) for row in rows}
        finally:
            await engine.dispose()

    role_permissions = asyncio.run(_load())

    expected = {
        (definition.role, definition.object, definition.action)
        for definition in PERMISSION_DEFINITIONS
    }
    assert role_permissions == expected
    assert len(role_permissions) == 17


def test_demo_orders_are_realistic_and_idempotent(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}")

    async def _load() -> tuple[list[FdeOrder], dict[int, int]]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            seed_settings = build_seed_settings()
            await seed_database(seed_settings, factory, demo=True)
            await seed_database(seed_settings, factory, demo=True)
            async with factory() as session:
                orders = (
                    (
                        await session.execute(
                            select(FdeOrder)
                            .options(selectinload(FdeOrder.publisher))
                            .order_by(FdeOrder.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                log_counts = dict(
                    (
                        await session.execute(
                            select(FdeOrderLog.order_id, func.count()).group_by(
                                FdeOrderLog.order_id
                            )
                        )
                    ).all()
                )
            return list(orders), log_counts
        finally:
            await engine.dispose()

    orders, log_counts = asyncio.run(_load())

    assert [order.code for order in orders] == [
        definition.code for definition in DEMO_ORDER_DEFINITIONS
    ]
    statuses = [order.status for order in orders]
    assert statuses.count("open") == 5
    assert statuses.count("in_progress") == 3
    assert statuses.count("completed") == 2

    for order in orders:
        assert order.publisher.full_name == "企业（演示）"
        if order.status == "open":
            assert order.engineer_id is None
            assert order.claimed_at is None
            assert order.escrow_status == "held"
            assert log_counts.get(order.id, 0) == 0
            continue
        assert order.engineer_id is not None
        assert order.claimed_at is not None
        assert 1 <= log_counts.get(order.id, 0) <= 3
        if order.status == "completed":
            assert order.completed_at is not None
            assert order.escrow_status == "released"
        else:
            assert order.completed_at is None
            assert order.escrow_status == "held"


def test_demo_wallet_ledger_is_consistent(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'wallet.db'}")

    async def _load() -> tuple[dict[str, int], dict[str, list[WalletTransaction]]]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            seed_settings = build_seed_settings()
            await seed_database(seed_settings, factory, demo=True)
            await seed_database(seed_settings, factory, demo=True)
            async with factory() as session:
                balances = dict(
                    (
                        await session.execute(
                            select(User.username, Wallet.balance_cents).join(
                                Wallet, Wallet.user_id == User.id
                            )
                        )
                    ).all()
                )
                rows = (
                    await session.execute(
                        select(WalletTransaction, User.username)
                        .join(Wallet, Wallet.id == WalletTransaction.wallet_id)
                        .join(User, User.id == Wallet.user_id)
                        .order_by(WalletTransaction.created_at, WalletTransaction.id)
                    )
                ).all()
            ledger: dict[str, list[WalletTransaction]] = {}
            for transaction, username in rows:
                ledger.setdefault(username, []).append(transaction)
            return balances, ledger
        finally:
            await engine.dispose()

    balances, ledger = asyncio.run(_load())

    assert balances == EXPECTED_DEMO_BALANCES
    # 每类资金事件的金额与方向都要与演示订单 / 兑换码一致。
    order_payments = [
        tx for transactions in ledger.values() for tx in transactions if tx.type == "order_payment"
    ]
    settlements = [
        tx
        for transactions in ledger.values()
        for tx in transactions
        if tx.type == "order_settlement"
    ]
    recharges = [
        tx for transactions in ledger.values() for tx in transactions if tx.type == "recharge"
    ]
    assert len(order_payments) == 10
    assert sum(tx.amount_cents for tx in order_payments) == 87_700_000
    assert all(tx.direction == "debit" for tx in order_payments)
    assert len(settlements) == 2
    assert sum(tx.amount_cents for tx in settlements) == 15_700_000
    assert all(tx.direction == "credit" for tx in settlements)
    assert len(recharges) == 3
    assert len(ledger["admin"]) == 1
    assert len(ledger["member"]) == 2
    assert len(ledger["enterprise"]) == 11
    assert len(ledger["engineer"]) == 2
    assert sum(len(transactions) for transactions in ledger.values()) == 16

    # 余额 = 流水 balance_after 链的终点，且每一步都自洽。
    for username, transactions in ledger.items():
        expected = 0
        for transaction in transactions:
            if transaction.direction == "credit":
                expected += transaction.amount_cents
            else:
                expected -= transaction.amount_cents
            assert transaction.balance_after_cents == expected
        assert balances[username] == expected


def test_seed_retires_legacy_roles_and_demo_accounts(tmp_path: Path) -> None:
    """手工写入旧角色 / 旧演示账号后跑 seed：角色退役、账号清理并迁移到 member。"""

    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'legacy.db'}")

    async def _run() -> tuple[Any, dict[str, Any]]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            async with factory() as session:
                authenticated = Role(name="authenticated", description="旧基线")
                viewer_role = Role(name="viewer", description="旧只读")
                operator_role = Role(name="operator", description="旧运营")
                session.add_all([authenticated, viewer_role, operator_role])
                await session.flush()
                viewer_role.parent_id = authenticated.id
                operator_role.parent_id = viewer_role.id

                operator = User(
                    username="operator",
                    email="operator@example.com",
                    hashed_password=hash_password("operator12345"),
                    full_name="运营（演示）",
                    is_active=True,
                )
                viewer = User(
                    username="viewer",
                    email="viewer@example.com",
                    hashed_password=hash_password("viewer12345"),
                    full_name="访客（演示）",
                    is_active=True,
                )
                session.add_all([operator, viewer])
                await session.flush()
                session.add_all(
                    [
                        UserRole(user_id=operator.id, role_id=operator_role.id),
                        UserRole(user_id=viewer.id, role_id=viewer_role.id),
                        Wallet(user_id=operator.id, balance_cents=200_000),
                        Wallet(user_id=viewer.id, balance_cents=50_000),
                        RedeemCode(
                            code="RDM-OLD-0001",
                            amount_cents=100_000,
                            status="used",
                            batch_no="RDM-OLD",
                            used_by_id=viewer.id,
                            used_at=utcnow(),
                            created_at=utcnow(),
                        ),
                        # viewer 被订单引用：不能删除，必须转为 member 保留。
                        FdeOrder(
                            code="FDE-OLD-0001",
                            title="旧演示订单",
                            industry="医疗健康",
                            description="历史数据",
                            delivery_days=5,
                            price_cents=100_000,
                            status="open",
                            escrow_status="held",
                            publisher_id=viewer.id,
                            created_at=utcnow(),
                            updated_at=utcnow(),
                        ),
                    ]
                )
                await session.commit()

            result = await seed_database(build_seed_settings(), factory, demo=True)

            async with factory() as session:
                role_names = set((await session.execute(select(Role.name))).scalars().all())
                operator_user = (
                    await session.execute(select(User).where(User.username == "operator"))
                ).scalar_one_or_none()
                viewer_user = (
                    await session.execute(select(User).where(User.username == "viewer"))
                ).scalar_one()
                member_user = (
                    await session.execute(select(User).where(User.username == "member"))
                ).scalar_one()
                viewer_roles = set(
                    (
                        await session.execute(
                            select(Role.name)
                            .join(UserRole, UserRole.role_id == Role.id)
                            .where(UserRole.user_id == viewer_user.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                legacy_code = (
                    await session.execute(
                        select(RedeemCode).where(RedeemCode.code == "RDM-OLD-0001")
                    )
                ).scalar_one()
                counts = {
                    "users": (
                        await session.execute(select(func.count()).select_from(User))
                    ).scalar_one(),
                    "roles": (
                        await session.execute(select(func.count()).select_from(Role))
                    ).scalar_one(),
                    "permissions": (
                        await session.execute(select(func.count()).select_from(Permission))
                    ).scalar_one(),
                    "wallets": (
                        await session.execute(select(func.count()).select_from(Wallet))
                    ).scalar_one(),
                }
            return result, {
                "role_names": role_names,
                "operator_user": operator_user,
                "viewer_roles": viewer_roles,
                "legacy_code_used_by": legacy_code.used_by_id,
                "member_id": member_user.id,
                "counts": counts,
            }
        finally:
            await engine.dispose()

    result, state = asyncio.run(_run())

    assert set(result.retired_roles) == {"viewer", "operator"}
    assert result.removed_users == ("operator",)
    assert state["role_names"] == {"authenticated", "member", "enterprise", "engineer", "admin"}
    assert state["operator_user"] is None
    assert state["viewer_roles"] == {"member"}
    assert state["legacy_code_used_by"] == state["member_id"]
    assert state["counts"] == {
        "users": 5,
        "roles": 5,
        "permissions": 17,
        "wallets": 5,
    }
