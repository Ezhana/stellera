#!/usr/bin/env bash
# deploy/ops/backup.sh —— 在 ops 工具镜像内备份 PostgreSQL（pg_dump + gzip）。
#
# 只在容器里运行，宿主不执行任何时间 / 文件 / find / chmod 逻辑：
#   just backup staging [label]
#   # 等价于
#   docker compose --profile ops run --rm [-e BACKUP_LABEL=<label>] backup
#
# 输入（环境变量，由 compose.yaml 的 backup 服务从 deploy/env/<env>.env 注入）：
#   PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE  数据库连接（默认 db:5432）
#   DEPLOY_ENV        环境名，用于文件名与清理前缀（默认 staging）
#   BACKUP_DIR        容器内备份目录（默认 /backups，挂载自 deploy/.state/backups）
#   BACKUP_LABEL      备份标签，拼进文件名（默认 manual）
#   BACKUP_KEEP_DAYS  保留天数，>0 时清理同前缀旧备份（默认 14）
#
# 行为：
#   文件名 <env>-<UTC 时间戳>-<label>.sql.gz；先写 *.partial，gzip -t 校验通过
#   后再 mv 成正式文件并 chmod 600；任何一步失败都以非零码退出，让发布中止。
#   pg_dump --no-owner --no-privileges --clean --if-exists：恢复时可安全地
#   DROP 旧对象重建，且不依赖原角色 / 授权（便于跨环境导回）。

set -euo pipefail

PGHOST="${PGHOST:-db}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-hub}"
PGDATABASE="${PGDATABASE:-hub}"
DEPLOY_ENV="${DEPLOY_ENV:-staging}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_LABEL="${BACKUP_LABEL:-manual}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

log() { printf '[backup] %s\n' "$*"; }
warn() { printf '[backup] 警告：%s\n' "$*" >&2; }
die() {
  printf '[backup] 错误：%s\n' "$*" >&2
  exit 1
}

[[ -n "${PGPASSWORD:-}" ]] ||
  die "PGPASSWORD 未设置；应由 compose 的 backup 服务从 deploy/env/<env>.env 注入"

# ---------- 备份目录 ----------
# docker compose 会用 root 自动创建不存在的宿主挂载点；容器内再以 HOST_UID
# 运行时就可能写不进去。这里先给出可操作的提示，而不是抛一个 EACCES。
if [[ ! -d "$BACKUP_DIR" ]]; then
  log "备份目录不存在，尝试创建：$BACKUP_DIR"
  mkdir -p "$BACKUP_DIR" 2>/dev/null ||
    die "无法创建备份目录：$BACKUP_DIR
  请在仓库根目录（宿主）先执行：
    mkdir -p deploy/.state/backups"
fi
if [[ ! -w "$BACKUP_DIR" ]]; then
  die "备份目录不可写：$BACKUP_DIR（容器内 UID:GID=$(id -u):$(id -g)）
  常见原因：宿主备份目录被自动创建成 root 属主，或 HOST_UID/HOST_GID 与目录属主不一致。
  处理：
    mkdir -p deploy/.state/backups
    sudo chown -R \"\$(id -u):\$(id -g)\" deploy/.state/backups   # 仅当目录属主不对
    Linux 上如宿主用户不是 1000，请在 deploy/env/<env>.env 设置 HOST_UID/HOST_GID"
fi
umask 077
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

# ---------- 命名 ----------
TIMESTAMP="$(date -u '+%Y%m%d-%H%M%S')"
# 标签只保留安全字符，避免拼出非法 / 含路径分隔符的文件名。
SAFE_LABEL="${BACKUP_LABEL//[^A-Za-z0-9_.-]/-}"
FILE="$BACKUP_DIR/${DEPLOY_ENV}-${TIMESTAMP}-${SAFE_LABEL}.sql.gz"
PARTIAL="${FILE}.partial"

cleanup() {
  rm -f "$PARTIAL"
}
trap cleanup EXIT

# ---------- 转储 ----------
log "备份数据库 ${PGDATABASE}@${PGHOST}:${PGPORT} -> ${FILE}"
if ! pg_dump --no-owner --no-privileges --clean --if-exists | gzip -c >"$PARTIAL"; then
  die "pg_dump 执行失败（检查 db 是否健康、PGUSER/PGPASSWORD 是否与数据卷一致）"
fi
[[ -s "$PARTIAL" ]] || die "备份文件为空：$PARTIAL"
if ! gzip -t "$PARTIAL" 2>/dev/null; then
  die "备份文件 gzip 校验失败：$PARTIAL"
fi

mv "$PARTIAL" "$FILE"
chmod 600 "$FILE"
trap - EXIT
SIZE="$(wc -c <"$FILE" | tr -d ' ')"
log "备份完成：${FILE}（${SIZE} 字节）"
log "宿主路径：deploy/.state/backups/$(basename "$FILE")（BACKUP_HOST_DIR 可覆盖）"

# ---------- 清理过期备份（仍在本容器内执行）----------
if [[ "$BACKUP_KEEP_DAYS" =~ ^[0-9]+$ ]] && ((BACKUP_KEEP_DAYS > 0)); then
  REMOVED="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "${DEPLOY_ENV}-*.sql.gz" \
    -mtime "+${BACKUP_KEEP_DAYS}" -print 2>/dev/null | wc -l | tr -d ' ')"
  if [[ "$REMOVED" != "0" ]]; then
    find "$BACKUP_DIR" -maxdepth 1 -type f -name "${DEPLOY_ENV}-*.sql.gz" \
      -mtime "+${BACKUP_KEEP_DAYS}" -delete 2>/dev/null || warn "清理旧备份时有文件删除失败"
    log "已清理 ${REMOVED} 个超过 ${BACKUP_KEEP_DAYS} 天的旧备份"
  fi
else
  log "BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS}（<=0 或非数字），跳过旧备份清理"
fi
