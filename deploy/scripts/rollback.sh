#!/usr/bin/env bash
# 回滚到上一个发布版本（只切换镜像 tag，不重新构建）。
#
# 原理：deploy.sh 每次成功后会把当前版本写入 deploy/.state/<env>/current，
# 旧版本写入 previous；本脚本读取 previous（或 --to 指定版本），用该 tag 重新
# compose up -d。因此回滚要求旧版本镜像仍在本机（不要执行 docker image prune）。
#
# 注意：本脚本不回滚数据库 schema。若本次发布包含 Alembic 迁移，旧代码可能与
# 新 schema 不兼容；需要时先用 db-restore.sh 恢复发布前备份（默认每次发布前自动备份）。
#
# 用法：
#   deploy/scripts/rollback.sh --env staging
#   deploy/scripts/rollback.sh --env staging --to v0.1.0
#
# 参数：
#   --env <名称>    环境名，默认 staging
#   --to <版本>     回滚到指定版本（默认取 state/previous）
#   --skip-backup   跳过回滚前数据库备份
#   --skip-smoke    跳过回滚后的冒烟测试
#   --timeout <秒>  等待 api 健康的超时，默认 180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
TO_VERSION=""
DO_BACKUP=1
DO_SMOKE=1
WAIT_TIMEOUT=180

usage() {
  cat <<'EOF'
回滚 Stellera Hub 测试环境到上一个发布版本。

用法：
  deploy/scripts/rollback.sh [--env <名称>] [--to <版本>] [选项]

参数：
  --env <名称>    环境名，默认 staging
  --to <版本>     回滚到指定版本（默认取 deploy/.state/<env>/previous）
  --skip-backup   跳过回滚前数据库备份
  --skip-smoke    跳过回滚后的冒烟测试
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
    --to)
      [[ $# -ge 2 ]] || die "--to 需要一个参数"
      TO_VERSION="$2"
      shift 2
      ;;
    --to=*)
      TO_VERSION="${1#*=}"
      shift
      ;;
    --skip-backup)
      DO_BACKUP=0
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
validate_deploy_env

CURRENT_VERSION="$(state_version current || true)"
TARGET_VERSION="${TO_VERSION:-$(state_version previous || true)}"

if [[ -z "$TARGET_VERSION" ]]; then
  die "没有可回滚的版本记录（$(state_dir)/previous 不存在）。
  首次部署还没有历史版本；也可以显式指定：deploy/scripts/rollback.sh --env $ENV_NAME --to <版本>"
fi
if [[ "$TARGET_VERSION" == "$CURRENT_VERSION" ]]; then
  die "目标版本与当前版本相同（${TARGET_VERSION}），无需回滚"
fi

RELEASE_VERSION="$TARGET_VERSION"
export RELEASE_VERSION

log_info "当前版本：${CURRENT_VERSION:-<未知>}"
log_info "回滚目标：$TARGET_VERSION"

# 回滚只切 tag，不构建：旧镜像必须还在本机。
for component in api web; do
  ref="$(image_ref "$component")"
  docker image inspect "$ref" >/dev/null 2>&1 ||
    die "回滚目标镜像不存在：$ref
  旧镜像可能已被清理。可改用相同版本重新部署：
    deploy/scripts/deploy.sh --env $ENV_NAME --version $TARGET_VERSION
  或恢复发布前数据库备份：deploy/scripts/db-restore.sh --env $ENV_NAME --file <备份文件>"
done

log_warn "回滚只切换应用镜像，不会回滚数据库 schema。"
log_warn "如果本次发布执行过 Alembic 迁移，旧代码可能与新 schema 不兼容；"
log_warn "必要时用 db-restore.sh 恢复 $(resolve_backup_dir) 下的发布前备份。"

if ((DO_BACKUP == 1)) && [[ "${BACKUP_BEFORE_DEPLOY:-true}" == "true" ]]; then
  if [[ -n "$(compose ps -q db 2>/dev/null || true)" ]]; then
    log_info "回滚前备份数据库..."
    "$SCRIPTS_DIR/db-backup.sh" --env "$ENV_NAME" --label "pre-rollback-$TARGET_VERSION" ||
      die "数据库备份失败，已中止回滚（确认可跳过时用 --skip-backup）"
  fi
fi

log_info "切换到 $TARGET_VERSION 并重启容器..."
compose up -d --remove-orphans

log_info "等待 api 健康检查通过（最长 ${WAIT_TIMEOUT}s）..."
if ! wait_for_container_health api "$WAIT_TIMEOUT"; then
  compose ps || true
  compose logs --tail=80 api 2>/dev/null || true
  die "回滚后 api 未在 ${WAIT_TIMEOUT}s 内就绪；请检查日志或恢复数据库备份"
fi

if ! wait_for_http "$(base_url)/healthz" 60; then
  compose ps || true
  die "回滚后 web 入口不可访问"
fi

if ((DO_SMOKE == 1)); then
  log_info "回滚后冒烟测试..."
  if ! "$SCRIPTS_DIR/smoke-test.sh" --env "$ENV_NAME"; then
    compose ps || true
    die "回滚后冒烟测试失败；数据库可能已随新版本迁移，请评估是否恢复备份"
  fi
fi

swap_release_state "$TARGET_VERSION" "rollback"

log_ok "已回滚到 ${TARGET_VERSION}（原版本：${CURRENT_VERSION:-<未知>}）"
log_info "访问地址：$(base_url)"
log_info "当前版本：$(state_version current || true)"
log_info "上一版本：$(state_version previous || true)"
compose ps
