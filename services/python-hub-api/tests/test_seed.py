"""种子脚本的幂等性与角色树。"""

from __future__ import annotations

import asyncio
from pathlib import Path

from sqlalchemy import func, select

from app.core.config import Settings
from app.db import create_all_tables, create_engine, create_session_factory
from app.models.rbac import Permission, Role, UserRole
from app.models.user import User
from app.scripts.seed import ROLE_DEFINITIONS, seed_database
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
            return first, second, users, roles, permissions, links
        finally:
            await engine.dispose()

    return asyncio.run(_run())


def test_seed_is_idempotent(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")

    first, second, users, roles, permissions, links = _run_seed(settings)

    assert first.created_users == ("admin", "operator", "viewer")
    assert len(first.created_roles) == len(ROLE_DEFINITIONS) == 4
    assert first.created_permissions == 10
    # 第二次执行不应重复创建任何东西。
    assert second.created_users == ()
    assert second.created_roles == ()
    assert second.created_permissions == 0
    assert users == 3
    assert roles == 4
    assert permissions == 10
    assert links == 3


def test_seed_demo_users_can_be_disabled(tmp_path: Path) -> None:
    settings = build_test_settings(f"sqlite+aiosqlite:///{tmp_path / 'seed-nodemo.db'}")
    settings = settings.model_copy(update={"seed_demo_users": False})

    first, _second, users, _roles, _permissions, links = _run_seed(settings)

    assert first.created_users == ("admin",)
    assert users == 1
    assert links == 1


def test_role_tree_is_linear(tmp_path: Path) -> None:
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
    }
