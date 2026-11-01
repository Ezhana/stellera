#!/usr/bin/env bash
# 用 db-backup.sh 生成的备份恢复测试环境数据库。
#
# 危险操作：会覆盖现有数据。默认要求交互输入 restore 确认，恢复期间先停掉 api，
# 恢复完成后重新拉起 api 并等待健康（entrypoint 会再跑一次迁移与 seed，均为幂等）。
#
# 用法：
#   deploy/scripts/db-restore.sh --env staging --file deploy/.state/backups/staging-20260101-120000-manual.sql.gz
#
# 参数：
#   --env <名称>    环境名，默认 staging
#   --file <路径>   备份文件（.sql.gz，db-backup.sh 的产物）
#   --yes           跳过交互确认（脚本/CI 中使用，务必确认文件正确）
#   --skip-smoke    恢复后不跑冒烟测试
#   --timeout <秒>  等待 api 健康的超时，默认 180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
BACKUP_FILE=""
ASSUME_YES=0
DO_SMOKE=1
WAIT_TIMEOUT=180

usage() {
  cat <<'EOF'
恢复 Stellera Hub 测试环境数据库（危险操作）。

用法：
  deploy/scripts/db-restore.sh --env <名称> --file <备份文件> [--yes] [--skip-smoke]

参数：
  --env <名称>    环境名，默认 staging
  --file <路径>   备份文件（.sql.gz）
  --yes           跳过交互确认
  --skip-smoke    恢复后跳过冒烟测试
  --timeout <秒>  等待 api 健康检查的超时时间，默认 180
  -h, --help      显示帮助
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
    --file)
      [[ $# -ge 2 ]] || die "--file 需要一个参数"
      BACKUP_FILE="$2"
      shift 2
      ;;
    --file=*)
      BACKUP_FILE="${1#*=}"
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    --skip-smoke)
      DO_SMOKE=0
      shift
      ;;
    --timeout)
      [[ $# -ge 2 ]] || die "--timeout 需要一个参数"
      WAIT_TIMEOUT="$2"
      shift 2
      ;;
    --timeout=*)
      WAIT_TIMEOUT="${1#*=}"
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

[[ -n "$BACKUP_FILE" ]] || die "缺少 --file 参数（备份文件路径）"
[[ -f "$BACKUP_FILE" ]] || die "备份文件不存在：$BACKUP_FILE"
gzip -t "$BACKUP_FILE" 2>/dev/null || die "备份文件不是有效的 gzip：$BACKUP_FILE"

if [[ -z "$(compose ps -q db 2>/dev/null || true)" ]]; then
  die "db 容器未运行，无法恢复；请先启动：deploy/scripts/deploy.sh --env $ENV_NAME --no-build"
fi

# 恢复过程中要停 api 再拉起，这里先解析当前发布版本并固定镜像 tag；
# 否则 compose 会因缺少 RELEASE_VERSION 回落到 :local 并触发构建。
# 允许使用者用 RELEASE_VERSION=<版本> 显式覆盖（容器已删除时的手工兜底）。
RELEASE_VERSION="${RELEASE_VERSION:-$(current_release_version || true)}"
if [[ -z "$RELEASE_VERSION" ]]; then
  die "无法确定当前发布版本（api 容器不存在且 $(state_dir)/current 为空）。
  先执行 deploy/scripts/deploy.sh --env ${ENV_NAME}，或手工指定：RELEASE_VERSION=<版本> deploy/scripts/db-restore.sh ..."
fi
export RELEASE_VERSION
docker image inspect "$(image_ref api)" >/dev/null 2>&1 ||
  die "当前版本镜像不存在：$(image_ref api)；请先重新部署该版本"

# 防呆：备份文件名默认以 <env>- 开头，跨环境恢复很容易把测试数据导错环境。
BACKUP_NAME="$(basename "$BACKUP_FILE")"
if [[ "$BACKUP_NAME" != "${ENV_NAME}-"* ]]; then
  log_warn "备份文件名不以 ${ENV_NAME}- 开头，可能属于其他环境：$BACKUP_NAME"
  if ((ASSUME_YES == 0)); then
    require_answer "restore-anyway" "确认仍要恢复？输入 restore-anyway 继续："
  fi
fi

log_warn "即将用 $BACKUP_FILE 覆盖环境 $ENV_NAME 的数据库 ${POSTGRES_DB}（现有数据会丢失）"
if ((ASSUME_YES == 0)); then
  require_answer "restore" "确认恢复请输入 restore："
fi

log_info "先停止 api，避免恢复期间写入..."
compose stop api >/dev/null 2>&1 || true

log_info "恢复数据库（psql，遇到错误即中止）..."
if ! gunzip -c "$BACKUP_FILE" |
  compose exec -T db sh -c 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null; then
  log_error "恢复失败，重新拉起 api（数据库可能处于中间状态，请检查后重试或换备份文件）"
  compose up -d --no-build api >/dev/null 2>&1 || true
  exit 1
fi

log_ok "数据恢复完成"
log_info "重新拉起 api..."
compose up -d --no-build api >/dev/null

log_info "等待 api 健康检查通过（最长 ${WAIT_TIMEOUT}s）..."
if ! wait_for_container_health api "$WAIT_TIMEOUT"; then
  compose ps || true
  compose logs --tail=80 api 2>/dev/null || true
  die "恢复后 api 未就绪，请检查日志"
fi

if ((DO_SMOKE == 1)); then
  log_info "恢复后冒烟测试..."
  "$SCRIPTS_DIR/smoke-test.sh" --env "$ENV_NAME" || die "恢复后冒烟测试失败，请检查数据与日志"
fi

log_ok "数据库恢复完成：$ENV_NAME"
