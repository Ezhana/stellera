"""种子脚本的幂等性、角色树、FDE 演示订单与钱包账本。"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db import create_all_tables, create_engine, create_session_factory
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, UserRole
from app.models.redeem import RedeemCode
from app.models.system_setting import SystemSetting
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction
from app.scripts.seed import load_demo, load_rbac, seed_database
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
    "operator": 200_000,
    "viewer": 150_000,
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
    assert len(first.created_roles) == len(ROLE_DEFINITIONS) == 6
    assert first.created_permissions == len(PERMISSION_DEFINITIONS) == 13
    assert first.created_orders == len(DEMO_ORDER_DEFINITIONS) == 10
    assert first.created_wallets == len(DEMO_WALLET_DEFINITIONS) == 5
    # 4 条演示充值 + 10 条订单托管 + 2 条完成结算 + 1 条已用兑换码入账。
    assert first.created_wallet_transactions == 17
    assert first.created_redeem_codes == len(DEMO_REDEEM_CODE_DEFINITIONS) == 3
    assert first.created_settings == 3

    # 第二次执行不应重复创建任何东西（含演示钱包、流水、兑换码与系统设置）。
    assert second.created_users == ()
    assert second.created_roles == ()
    assert second.created_permissions == 0
    assert second.created_orders == 0
    assert second.created_wallets == 0
    assert second.created_wallet_transactions == 0
    assert second.created_redeem_codes == 0
    assert second.created_settings == 0

    assert counts["users"] == 1 + len(DEMO_USER_DEFINITIONS) == 5
    assert counts["roles"] == 6
    assert counts["permissions"] == 13
    assert counts["links"] == 1 + len(DEMO_USER_DEFINITIONS) == 5
    assert counts["orders"] == 10
    assert counts["logs"] == 11
    assert counts["wallets"] == 5
    assert counts["wallet_transactions"] == 17
    assert counts["redeem_codes"] == 3
    assert counts["settings"] == 3
    assert counts["balances"] == EXPECTED_DEMO_BALANCES


def test_seed_without_demo_only_creates_admin(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed-nodemo.db'}")

    first, second, counts = _run_seed(settings, demo=False)

    assert first.created_users == ("admin",)
    assert first.created_orders == 0
    assert first.created_wallets == 0
    assert first.created_wallet_transactions == 0
    assert first.created_redeem_codes == 0
    # 系统设置即使没有演示数据也会写入默认值。
    assert first.created_settings == 3
    assert second.created_settings == 0
    assert counts["users"] == 1
    assert counts["links"] == 1
    assert counts["orders"] == 0
    assert counts["logs"] == 0
    assert counts["wallets"] == 0
    assert counts["wallet_transactions"] == 0
    assert counts["redeem_codes"] == 0
    assert counts["settings"] == 3


def test_role_tree_is_linear_with_fde_roles(tmp_path: Path) -> None:
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
        "viewer": "authenticated",
        "operator": "viewer",
        "admin": "operator",
        "enterprise": "authenticated",
        "engineer": "authenticated",
    }


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
    assert len(order_payments) == 10
    assert sum(tx.amount_cents for tx in order_payments) == 87_700_000
    assert all(tx.direction == "debit" for tx in order_payments)
    assert len(settlements) == 2
    assert sum(tx.amount_cents for tx in settlements) == 15_700_000
    assert all(tx.direction == "credit" for tx in settlements)
    assert len(ledger["admin"]) == 1
    assert len(ledger["operator"]) == 1
    assert len(ledger["viewer"]) == 2
    assert len(ledger["enterprise"]) == 11
    assert len(ledger["engineer"]) == 2

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
