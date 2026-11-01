#!/usr/bin/env bash
# 查看测试环境状态：容器、健康检查、当前/上一发布版本、入口可用性、最近备份。
#
# 用法：
#   deploy/scripts/status.sh --env staging

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"

usage() {
  cat <<'EOF'
查看 Stellera Hub 测试环境状态。

用法：
  deploy/scripts/status.sh [--env <名称>]

参数：
  --env <名称>    环境名，默认 staging
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

log_info "环境：$ENV_NAME   project：$COMPOSE_PROJECT_NAME"
log_info "入口：$(base_url)   API：$(api_base_url)"

# ---------- 发布版本 ----------
CURRENT_LINE=""
PREVIOUS_LINE=""
if [[ -f "$(state_dir)/current" ]]; then
  CURRENT_LINE="$(cat "$(state_dir)/current")"
fi
if [[ -f "$(state_dir)/previous" ]]; then
  PREVIOUS_LINE="$(cat "$(state_dir)/previous")"
fi
printf '\n发布状态：\n'
if [[ -n "$CURRENT_LINE" ]]; then
  printf '  current  : %s\t%s\n' "$(printf '%s' "$CURRENT_LINE" | cut -f1)" "$(printf '%s' "$CURRENT_LINE" | cut -f2)"
else
  printf '  current  : <无记录>\n'
fi
if [[ -n "$PREVIOUS_LINE" ]]; then
  printf '  previous : %s\t%s\n' "$(printf '%s' "$PREVIOUS_LINE" | cut -f1)" "$(printf '%s' "$PREVIOUS_LINE" | cut -f2)"
else
  printf '  previous : <无记录>\n'
fi

# ---------- 容器 ----------
printf '\n容器状态：\n'
for service in db api web; do
  cid="$(compose ps -q "$service" 2>/dev/null || true)"
  if [[ -z "$cid" ]]; then
    printf '  %-4s 未运行\n' "$service"
    continue
  fi
  state="$(docker inspect --format '{{.State.Status}}' "$cid" 2>/dev/null || true)"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}' "$cid" 2>/dev/null || true)"
  image="$(docker inspect --format '{{.Config.Image}}' "$cid" 2>/dev/null || true)"
  printf '  %-4s %-10s health=%-10s image=%s\n' "$service" "${state:-?}" "${health:-?}" "${image:-?}"
done

# ---------- 入口 ----------
printf '\n入口检查：\n'
web_code="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' "$(base_url)/healthz" 2>/dev/null || true)"
printf '  web /healthz : %s\n' "${web_code:-连接失败}"
api_code="$(curl -sS --max-time 5 -o /dev/null -w '%{http_code}' "$(api_base_url)/health/ready" 2>/dev/null || true)"
printf '  api /health/ready（%s）: %s\n' "$(api_base_url)" "${api_code:-连接失败}"

# ---------- 备份 ----------
BACKUP_ROOT="$(resolve_backup_dir)"
printf '\n最近备份（%s）：\n' "$BACKUP_ROOT"
if [[ -d "$BACKUP_ROOT" ]]; then
  count=0
  while IFS= read -r backup; do
    [[ -n "$backup" ]] || continue
    count=$((count + 1))
    printf '  %s（%s）\n' "$(basename "$backup")" "$(human_size "$(wc -c <"$backup" | tr -d ' ')")"
  done <<EOF
$(find "$BACKUP_ROOT" -maxdepth 1 -type f -name "${ENV_NAME}-*.sql.gz" -print 2>/dev/null | sort -r | head -n 5)
EOF
  if ((count == 0)); then
    printf '  <暂无备份>\n'
  fi
else
  printf '  <备份目录不存在>\n'
fi

# ---------- compose 概览 ----------
printf '\ncompose 概览：\n'
compose ps
