#!/usr/bin/env bash
# 停止并删除测试环境容器。
#
# 默认保留数据卷（pgdata），重新 deploy 后数据还在；
# 只有显式 --volumes 才会删除数据库数据，需要交互输入 delete-data 确认。
#
# 用法：
#   deploy/scripts/down.sh --env staging              # 停容器，保留数据
#   deploy/scripts/down.sh --env staging --volumes    # 连数据一起删（危险）
#   deploy/scripts/down.sh --env staging --volumes --yes

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
REMOVE_VOLUMES=0
ASSUME_YES=0

usage() {
  cat <<'EOF'
停止 Stellera Hub 测试环境。

用法：
  deploy/scripts/down.sh [--env <名称>] [--volumes [--yes]]

参数：
  --env <名称>    环境名，默认 staging
  --volumes       同时删除数据卷（会丢失数据库数据，需输入 delete-data 确认）
  --yes           配合 --volumes 跳过交互确认
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
    --volumes)
      REMOVE_VOLUMES=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
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

if ((REMOVE_VOLUMES == 1)); then
  if ((ASSUME_YES == 0)); then
    require_answer "delete-data" "确认删除环境 $ENV_NAME 的数据库数据卷？输入 delete-data 继续："
  fi
  log_warn "删除容器与数据卷（数据库数据不可恢复）..."
  compose down -v --remove-orphans
  log_ok "已停止并删除环境 ${ENV_NAME}（含数据卷）"
else
  log_info "停止容器（保留数据卷 pgdata）..."
  compose down --remove-orphans
  log_ok "已停止环境 ${ENV_NAME}（数据保留）"
fi
