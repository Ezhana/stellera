#!/usr/bin/env sh
# 容器入口：先执行数据库迁移，再幂等写入种子数据，最后 exec 真正的启动命令。
# 这样 `docker run` / compose 起来后无需人工初始化数据库。
set -eu

echo "[entrypoint] alembic upgrade head"
alembic upgrade head

echo "[entrypoint] seeding roles/permissions/users"
python -m app.scripts.seed

exec "$@"
