#!/usr/bin/env sh
# 容器入口：默认行为（serve）先执行数据库迁移，再幂等写入种子数据，最后 exec 启动命令。
# 同一镜像也作为一次性任务入口，由 compose 的 `run --rm <service>` 复用：
#
#   entrypoint.sh [serve]   迁移 + seed + 启动 API（默认）
#   entrypoint.sh migrate   只执行 alembic upgrade head
#   entrypoint.sh seed      只执行幂等种子脚本
#   entrypoint.sh smoke     对入口（SMOKE_BASE_URL，默认 http://web）跑冒烟检查
#   entrypoint.sh <命令…>   透传执行任意命令（例如 sh）
#
# shift 掉子命令后再 exec，保证 PID 1 就是目标进程，SIGTERM 能正常转发。
set -eu

cmd="${1:-serve}"
if [ "$#" -gt 0 ]; then
  shift
fi

case "$cmd" in
  serve)
    echo "[entrypoint] alembic upgrade head"
    alembic upgrade head

    echo "[entrypoint] seeding roles/permissions/users"
    python -m app.scripts.seed

    exec fastapi run --host 0.0.0.0 --port 8000 "$@"
    ;;
  migrate)
    echo "[entrypoint] alembic upgrade head"
    exec alembic upgrade head "$@"
    ;;
  seed)
    echo "[entrypoint] seeding roles/permissions/users"
    exec python -m app.scripts.seed "$@"
    ;;
  smoke)
    exec python -m app.scripts.smoke "$@"
    ;;
  *)
    exec "$cmd" "$@"
    ;;
esac
