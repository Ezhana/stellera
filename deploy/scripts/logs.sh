#!/usr/bin/env bash
# 查看测试环境容器日志（默认跟随，等价于 docker compose logs -f）。
#
# 用法：
#   deploy/scripts/logs.sh --env staging            # 全部服务，跟随
#   deploy/scripts/logs.sh --env staging api        # 只看 api
#   deploy/scripts/logs.sh --env staging --tail 500 --no-follow web

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
TAIL=200
FOLLOW=1
SERVICE=""

usage() {
  cat <<'EOF'
查看 Stellera Hub 测试环境日志。

用法：
  deploy/scripts/logs.sh [--env <名称>] [--tail <行数>] [--no-follow] [服务名]

参数：
  --env <名称>    环境名，默认 staging
  --tail <行数>   显示最近多少行，默认 200
  --no-follow     输出后立即退出（默认跟随）
  服务名          可选 db / api / web；不传则输出全部
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
    --tail)
      [[ $# -ge 2 ]] || die "--tail 需要一个参数"
      TAIL="$2"
      shift 2
      ;;
    --tail=*)
      TAIL="${1#*=}"
      shift
      ;;
    --no-follow)
      FOLLOW=0
      shift
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*)
      die "未知参数：$1（-h 查看帮助）"
      ;;
    *)
      SERVICE="$1"
      shift
      ;;
  esac
done

require_docker
init_deploy_context "$ENV_NAME"

case "$SERVICE" in
  "" | db | api | web) ;;
  *) die "服务名只能是 db / api / web，收到：$SERVICE" ;;
esac
[[ "$TAIL" =~ ^[0-9]+$ ]] || die "--tail 必须是数字：$TAIL"

if [[ -n "$SERVICE" ]]; then
  if ((FOLLOW == 1)); then
    compose logs --tail "$TAIL" -f "$SERVICE"
  else
    compose logs --tail "$TAIL" "$SERVICE"
  fi
else
  if ((FOLLOW == 1)); then
    compose logs --tail "$TAIL" -f
  else
    compose logs --tail "$TAIL"
  fi
fi
