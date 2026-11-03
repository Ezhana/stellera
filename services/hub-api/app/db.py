"""数据库引擎与会话工厂。

测试用 SQLite（aiosqlite），生产用 PostgreSQL（asyncpg），模型本身不依赖具体方言。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.models.base import Base


def is_sqlite_url(url: str) -> bool:
    return url.startswith("sqlite")


def create_engine(settings: Settings) -> AsyncEngine:
    kwargs: dict[str, object] = {
        "echo": "db_echo" in settings.debug,
        "pool_pre_ping": True,
    }
    if not is_sqlite_url(settings.database_url):
        kwargs.update({"pool_size": 5, "max_overflow": 10})
    engine = create_async_engine(settings.database_url, **kwargs)

    if is_sqlite_url(settings.database_url):
        # SQLite 默认不校验外键；测试里希望和 PostgreSQL 行为一致。
        sync_engine: Engine = engine.sync_engine

        @event.listens_for(sync_engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def create_all_tables(engine: AsyncEngine) -> None:
    """按模型建表。生产环境用 Alembic；测试与临时本地库用这个函数。"""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def drop_all_tables(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
