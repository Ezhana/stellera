#!/usr/bin/env bash
# deploy/ops/restore.sh —— 在 ops 工具镜像内用备份恢复 PostgreSQL。
#
# 危险操作：会覆盖现有数据。默认要求交互输入确认，恢复期间 api 由 just 负责停掉。
#   just restore staging <备份文件名>
#   # 等价于
#   docker compose stop api
#   docker compose --profile ops run --rm -e RESTORE_FILE=/backups/<备份文件名> restore
#   docker compose start api
#
# 输入（环境变量）：
#   RESTORE_FILE      备份文件路径（容器内 /backups/<文件名>；也接受备份目录下的文件名），必填
#   RESTORE_CONFIRM   非交互确认；值为 restore 时跳过交互输入（CI / 无 TTY）
#   PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE  数据库连接（默认 db:5432）
#   DEPLOY_ENV        环境名（默认 staging），用于跨环境恢复提醒
#   BACKUP_DIR        容器内备份目录（默认 /backups），用于拼相对路径与提示
#
# 行为：校验文件存在且是有效 gzip -> 确认 -> 终止该库其它会话 ->
#       gunzip -c | psql -v ON_ERROR_STOP=1；失败非零退出。

set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-hub}"
PGDATABASE="${PGDATABASE:-hub}"
DEPLOY_ENV="${DEPLOY_ENV:-staging}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
RESTORE_FILE="${RESTORE_FILE:-}"
RESTORE_CONFIRM="${RESTORE_CONFIRM:-}"

log() { printf '[restore] %s\n' "$*"; }
warn() { printf '[restore] 警告：%s\n' "$*" >&2; }
die() {
  printf '[restore] 错误：%s\n' "$*" >&2
  exit 1
}

[[ -n "${PGPASSWORD:-}" ]] ||
  die "PGPASSWORD 未设置；应由 compose 的 restore 服务从 deploy/env/<env>.env 注入"
[[ -n "$RESTORE_FILE" ]] ||
  die "RESTORE_FILE 未设置。
  用法：just restore ${DEPLOY_ENV} <备份文件名>
  等价：docker compose --profile ops run --rm -e RESTORE_FILE=/backups/<备份文件名> restore"

# 允许只传文件名（相对路径按容器内备份目录解析），便于手工调试。
if [[ ! -f "$RESTORE_FILE" && "$RESTORE_FILE" != /* ]]; then
  RESTORE_FILE="$BACKUP_DIR/$RESTORE_FILE"
fi

if [[ ! -f "$RESTORE_FILE" ]]; then
  {
    printf '[restore] 错误：备份文件不存在：%s\n' "$RESTORE_FILE" >&2
    if [[ -d "$BACKUP_DIR" ]]; then
      printf '[restore] 备份目录 %s 下最近的备份（宿主路径 deploy/.state/backups/）：\n' "$BACKUP_DIR" >&2
      find "$BACKUP_DIR" -maxdepth 1 -type f -name '*.sql.gz' -printf '%f\n' 2>/dev/null |
        sort -r | head -n 10 | sed 's/^/  - /' >&2 || true
    fi
    printf '[restore] 提示：先在宿主机确认目录与文件：\n  ls -lt deploy/.state/backups\n' >&2
  } >&2
  exit 1
fi
gzip -t "$RESTORE_FILE" 2>/dev/null ||
  die "备份文件不是有效的 gzip（可能拷贝不完整）：$RESTORE_FILE"

# ---------- 确认 ----------
BACKUP_NAME="$(basename "$RESTORE_FILE")"
CROSS_ENV=0
case "$BACKUP_NAME" in
  "${DEPLOY_ENV}-"*) ;;
  *) CROSS_ENV=1 ;;
esac
if ((CROSS_ENV == 1)); then
  warn "备份文件名不以 ${DEPLOY_ENV}- 开头，可能属于其他环境：${BACKUP_NAME}"
fi

if [[ -n "$RESTORE_CONFIRM" ]]; then
  [[ "$RESTORE_CONFIRM" == "restore" ]] ||
    die "RESTORE_CONFIRM 必须为 restore（收到：${RESTORE_CONFIRM}）"
  log "已通过 RESTORE_CONFIRM=restore 跳过交互确认"
else
  [[ -t 0 ]] || die "非交互环境无法确认（stdin 不是 TTY）。
  如确认要恢复，请显式设置 RESTORE_CONFIRM=restore：
    docker compose --profile ops run --rm -e RESTORE_FILE=/backups/${BACKUP_NAME} -e RESTORE_CONFIRM=restore restore"
  printf '[restore] 即将用 %s 覆盖环境 %s 的数据库 %s（现有数据会丢失）。\n' \
    "$BACKUP_NAME" "$DEPLOY_ENV" "$PGDATABASE" >&2
  if ((CROSS_ENV == 1)); then
    printf '[restore] 备份文件名与当前环境不一致，确认请输入 restore-anyway：' >&2
    read -r ANSWER || die "读取输入失败（非交互环境请设置 RESTORE_CONFIRM=restore）"
    [[ "$ANSWER" == "restore-anyway" ]] || die "已取消（需要输入 restore-anyway 确认）"
  else
    printf '[restore] 确认恢复请输入 restore：' >&2
    read -r ANSWER || die "读取输入失败（非交互环境请设置 RESTORE_CONFIRM=restore）"
    [[ "$ANSWER" == "restore" ]] || die "已取消（需要输入 restore 确认）"
  fi
fi

# ---------- 恢复 ----------
log "连接 ${PGUSER}@${PGHOST}:${PGPORT}/${PGDATABASE}"
psql -v ON_ERROR_STOP=1 -Atc 'select 1' >/dev/null ||
  die "无法连接数据库；检查 db 是否健康、PGUSER/PGPASSWORD 是否与数据卷一致"

log "终止该数据库上的其它会话（避免恢复时被占用）..."
psql -v ON_ERROR_STOP=1 -Atc \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid();" \
  >/dev/null || die "终止数据库会话失败（权限不足？）"

log "恢复 ${BACKUP_NAME} -> ${PGDATABASE}（psql -v ON_ERROR_STOP=1，遇到错误即中止）..."
# 备份文件里的 set_config 等查询结果不需要回显；错误与 NOTICE 仍走 stderr。
if ! gunzip -c "$RESTORE_FILE" | psql -v ON_ERROR_STOP=1 -q -X >/dev/null; then
  die "恢复失败（数据库可能处于中间状态）。
  处理：换一个备份文件重试本命令，或检查 db 日志：just logs ${DEPLOY_ENV} db"
fi

log "恢复完成：${DEPLOY_ENV} <- ${BACKUP_NAME}"
log "api 由 just restore 自动重新拉起；如手工执行，请再运行：just up ${DEPLOY_ENV}"
