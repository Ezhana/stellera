"""种子脚本的幂等性、角色树与 FDE 演示订单。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.db import create_all_tables, create_engine, create_session_factory
from app.models.fde import FdeOrder, FdeOrderLog
from app.models.rbac import Permission, Role, UserRole
from app.models.user import User
from app.scripts.seed import DEMO_ORDER_DEFINITIONS, ROLE_DEFINITIONS, seed_database
from tests.conftest import build_test_settings


def _run_seed(settings: Settings):
    async def _run() -> tuple:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            first = await seed_database(settings, factory)
            second = await seed_database(settings, factory)
            async with factory() as session:
                users = (await session.execute(select(func.count()).select_from(User))).scalar_one()
                roles = (await session.execute(select(func.count()).select_from(Role))).scalar_one()
                permissions = (
                    await session.execute(select(func.count()).select_from(Permission))
                ).scalar_one()
                links = (
                    await session.execute(select(func.count()).select_from(UserRole))
                ).scalar_one()
                orders = (
                    await session.execute(select(func.count()).select_from(FdeOrder))
                ).scalar_one()
                logs = (
                    await session.execute(select(func.count()).select_from(FdeOrderLog))
                ).scalar_one()
            return first, second, users, roles, permissions, links, orders, logs
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def test_seed_is_idempotent(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")

    first, second, users, roles, permissions, links, orders, logs = _run_seed(settings)

    assert first.created_users == ("admin", "operator", "viewer", "enterprise", "engineer")
    assert len(first.created_roles) == len(ROLE_DEFINITIONS) == 6
    assert first.created_permissions == 10
    assert first.created_orders == 10
    # 第二次执行不应重复创建任何东西（含演示订单与工作日志）。
    assert second.created_users == ()
    assert second.created_roles == ()
    assert second.created_permissions == 0
    assert second.created_orders == 0
    assert users == 5
    assert roles == 6
    assert permissions == 10
    assert links == 5
    assert orders == 10
    assert logs == 11


def test_seed_demo_users_can_be_disabled(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed-nodemo.db'}")
    settings = settings.model_copy(update={"seed_demo_users": False})

    first, _second, users, _roles, _permissions, links, orders, logs = _run_seed(settings)

    assert first.created_users == ("admin",)
    assert first.created_orders == 0
    assert users == 1
    assert links == 1
    assert orders == 0
    assert logs == 0


def test_role_tree_is_linear_with_fde_roles(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'roles.db'}")

    async def _load() -> dict[str, str | None]:
        engine = create_engine(settings)
        factory = create_session_factory(engine)
        try:
            await create_all_tables(engine)
            await seed_database(settings, factory)
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
            await seed_database(settings, factory)
            await seed_database(settings, factory)
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
