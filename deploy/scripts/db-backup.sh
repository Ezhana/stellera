#!/usr/bin/env bash
# 备份测试环境 PostgreSQL（pg_dump 自定义压缩的 SQL 文本，gzip 存储）。
#
# 备份文件命名：<env>-<时间戳>-<label>.sql.gz
# 默认目录：deploy/.state/backups（可用 BACKUP_DIR 覆盖，相对路径按 deploy/ 解析）。
# 会自动清理超过 BACKUP_KEEP_DAYS 天的旧备份（默认 14 天）。
#
# 用法：
#   deploy/scripts/db-backup.sh --env staging
#   deploy/scripts/db-backup.sh --env staging --label manual-check
#   deploy/scripts/db-backup.sh --env staging --allow-missing   # db 未运行时不算失败
#
# 恢复：deploy/scripts/db-restore.sh --env staging --file <备份文件>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
LABEL="manual"
ALLOW_MISSING=0

usage() {
  cat <<'EOF'
备份 Stellera Hub 测试环境数据库。

用法：
  deploy/scripts/db-backup.sh [--env <名称>] [--label <标签>] [--allow-missing]

参数：
  --env <名称>       环境名，默认 staging
  --label <标签>     备份标签（会拼进文件名），默认 manual
  --allow-missing    db 容器未运行时只告警并退出 0（首次部署前备份用）
  -h, --help         显示帮助
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)
      [[ $# -ge 2 ]] || die "--env 需要一个参数"
      ENV_NAME="$2"
      shift 2
      ;;
    --env=*)
      ENV_NAME="${1#*=}"
      shift
      ;;
    --label)
      [[ $# -ge 2 ]] || die "--label 需要一个参数"
      LABEL="$2"
      shift 2
      ;;
    --label=*)
      LABEL="${1#*=}"
      shift
      ;;
    --allow-missing)
      ALLOW_MISSING=1
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      die "未知参数：$1（-h 查看帮助）"
      ;;
  esac
done

require_docker
init_deploy_context "$ENV_NAME"
require_var POSTGRES_USER
require_var POSTGRES_PASSWORD
require_var POSTGRES_DB

if [[ -z "$(compose ps -q db 2>/dev/null || true)" ]]; then
  if ((ALLOW_MISSING == 1)); then
    log_warn "db 容器未运行（首次部署），跳过备份"
    exit 0
  fi
  die "db 容器未运行，无法备份；首次部署可加 --allow-missing"
fi

BACKUP_ROOT="$(resolve_backup_dir)"
mkdir -p "$BACKUP_ROOT"
chmod 700 "$BACKUP_ROOT" 2>/dev/null || true

TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
SAFE_LABEL="${LABEL//[^A-Za-z0-9_.-]/-}"
FILE="$BACKUP_ROOT/${ENV_NAME}-${TIMESTAMP}-${SAFE_LABEL}.sql.gz"
PARTIAL="${FILE}.partial"

cleanup() {
  rm -f "$PARTIAL"
}
trap cleanup EXIT

log_info "备份数据库：$POSTGRES_DB -> $FILE"
# --clean --if-exists：恢复时先 DROP 再建，避免残留旧对象；
# --no-owner/--no-privileges：恢复时不依赖原角色与授权，便于跨环境导回。
if ! compose exec -T db sh -c \
  'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --clean --if-exists' |
  gzip -c >"$PARTIAL"; then
  die "pg_dump 执行失败（检查 api/db 日志与数据库连接）"
fi

if ! gzip -t "$PARTIAL" 2>/dev/null; then
  die "备份文件校验失败：$PARTIAL"
fi

mv "$PARTIAL" "$FILE"
chmod 600 "$FILE"
SIZE="$(wc -c <"$FILE" | tr -d ' ')"
trap - EXIT

log_ok "备份完成：${FILE}（$(human_size "$SIZE")）"

# ---------- 清理过期备份 ----------
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
if [[ "$KEEP_DAYS" =~ ^[0-9]+$ ]] && ((KEEP_DAYS > 0)); then
  REMOVED="$(find "$BACKUP_ROOT" -maxdepth 1 -type f -name "${ENV_NAME}-*.sql.gz" -mtime "+$KEEP_DAYS" -print 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$REMOVED" != "0" ]]; then
    find "$BACKUP_ROOT" -maxdepth 1 -type f -name "${ENV_NAME}-*.sql.gz" -mtime "+$KEEP_DAYS" -delete 2>/dev/null || true
    log_info "已清理 $REMOVED 个超过 ${KEEP_DAYS} 天的旧备份"
  fi
fi
