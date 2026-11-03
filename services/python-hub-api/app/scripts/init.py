"""数据库初始化 job：先执行 Alembic 迁移，再写入种子数据。"""

from __future__ import annotations

import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.scripts.seed import run_seed

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description="数据库初始化：Alembic 迁移 + 幂等种子数据")
    parser.add_argument("--demo", action="store_true", help="同时写入演示账号与 FDE 演示订单")
    args = parser.parse_args()

    command.upgrade(Config(str(SERVICE_ROOT / "alembic.ini")), "head")
    run_seed(demo=args.demo)


if __name__ == "__main__":
    main()
