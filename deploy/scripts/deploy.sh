#!/usr/bin/env bash
# 测试环境一键部署（Docker only）。
#
# 流程：校验环境文件与变量 -> 构建带版本 tag 的镜像 -> 发布前备份数据库 ->
#       compose up -d -> 等待 api/web 健康 -> 冒烟测试 -> 记录发布状态。
#
# 典型用法（在测试机上，仓库根目录）：
#   git pull
#   deploy/scripts/init-env.sh --env staging      # 仅首次
#   deploy/scripts/deploy.sh --env staging
#
# 常用参数：
#   --env <名称>      环境名，默认 staging，读取 deploy/env/<名称>.env
#   --version <版本>  指定发布版本（默认取 git describe --tags --always --dirty）
#   --no-build        不构建，直接用现有镜像（镜像必须已存在）
#   --no-cache        构建时不使用缓存（依赖或基础镜像刷新后使用）
#   --skip-backup     跳过发布前数据库备份（不推荐）
#   --skip-smoke      跳过冒烟测试（不推荐）
#   --timeout <秒>    等待 api 健康的超时，默认 180

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
VERSION_INPUT=""
DO_BUILD=1
NO_CACHE=0
DO_BACKUP=1
DO_SMOKE=1
WAIT_TIMEOUT=180

usage() {
  cat <<'EOF'
部署 Stellera Hub 到测试环境（Docker Compose）。

用法：
  deploy/scripts/deploy.sh [--env <名称>] [--version <版本>] [选项]

参数：
  --env <名称>      环境名，默认 staging；读取 deploy/env/<名称>.env
  --version <版本>  指定发布版本 tag（默认 git describe --tags --always --dirty）
  --no-build        跳过构建，直接使用现有镜像
  --no-cache        构建时禁用缓存
  --skip-backup     跳过发布前数据库备份
  --skip-smoke      跳过冒烟测试
  --timeout <秒>    等待 api 健康检查的超时时间，默认 180
  -h, --help        显示帮助
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
    --version)
      [[ $# -ge 2 ]] || die "--version 需要一个参数"
      VERSION_INPUT="$2"
      shift 2
      ;;
    --version=*)
      VERSION_INPUT="${1#*=}"
      shift
      ;;
    --no-build)
      DO_BUILD=0
      shift
      ;;
    --no-cache)
      NO_CACHE=1
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

if [[ -n "$VERSION_INPUT" ]]; then
  RELEASE_VERSION="$VERSION_INPUT"
else
  RELEASE_VERSION="$(resolve_release_version)"
fi
[[ "$RELEASE_VERSION" =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$ ]] ||
  die "版本号不合法：${RELEASE_VERSION}（只允许字母、数字、_ . -，且不超过 128 字符）"
export RELEASE_VERSION

# 测试机上的发布应来自干净、已提交的版本；dirty 只提示不阻断，方便联调。
if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
  if [[ -n "$(git -C "$REPO_ROOT" status --porcelain 2>/dev/null || true)" ]]; then
    log_warn "工作区有未提交改动，镜像 tag 会带 -dirty；建议先 git pull 并提交后再发布"
  fi
fi

show_diagnostics() {
  log_warn "当前容器状态："
  compose ps || true
  log_warn "最近日志（api / web）："
  compose logs --tail=80 api web 2>/dev/null || true
}

log_info "环境：${ENV_NAME}（project: ${COMPOSE_PROJECT_NAME}）"
log_info "版本：$RELEASE_VERSION"
log_info "入口：$(base_url)  （API 仅绑定 ${API_BIND:-127.0.0.1}:${API_PORT:-8000}）"

# 已有数据库时先验证 env 里的密码真能连上；否则 init-env --force 换了密码后，
# 要等到构建完、容器起来才暴露问题。这一步失败不会改动任何数据。
# 注意：postgres 官方镜像的 pg_hba 对容器内 127.0.0.1 是 trust，必须连容器网络 IP
# 才能走到 scram 密码校验，所以这里显式取 db 容器 IP。
existing_db_cid="$(compose ps -q db 2>/dev/null || true)"
if [[ -n "$existing_db_cid" ]]; then
  db_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$existing_db_cid" 2>/dev/null || true)"
  # 多网络时 IP 会叠加输出，取第一个；db 未 healthy 时跳过预检，避免把“正在启动”误报成密码错误。
  db_ip="$(docker inspect --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' "$existing_db_cid" 2>/dev/null | awk 'NF { print $1; exit }')"
  if [[ "$db_health" != "healthy" ]]; then
    log_warn "db 容器未就绪（当前：${db_health:-未知}），跳过数据库密码预检"
  elif [[ -z "$db_ip" ]]; then
    log_warn "未解析到 db 容器 IP，跳过数据库密码预检"
  elif ! compose exec -T -e PGPASSWORD="$POSTGRES_PASSWORD" db \
    psql -h "$db_ip" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c 'select 1' >/dev/null 2>&1; then
    die "无法用当前 env 里的账号连接数据库（POSTGRES_PASSWORD 可能与已有数据卷不一致）。
  如果刚对已有环境执行过 init-env --force：请同步数据库密码，或 down.sh --volumes 重建（会丢数据）"
  fi
fi

# ---------- 1. 构建镜像 ----------
if ((DO_BUILD == 1)); then
  log_info "构建镜像（首次构建需拉取依赖，可能耗时几分钟）..."
  if ((NO_CACHE == 1)); then
    compose build --no-cache
  else
    compose build
  fi
else
  log_info "跳过构建（--no-build）"
fi

for component in api web; do
  ref="$(image_ref "$component")"
  docker image inspect "$ref" >/dev/null 2>&1 ||
    die "镜像不存在：$ref
  去掉 --no-build 重新构建，或先执行 deploy/scripts/deploy.sh --env $ENV_NAME"
done

# ---------- 2. 发布前备份 ----------
if ((DO_BACKUP == 1)) && [[ "${BACKUP_BEFORE_DEPLOY:-true}" == "true" ]]; then
  db_cid="$(compose ps -q db 2>/dev/null || true)"
  if [[ -n "$db_cid" ]]; then
    log_info "发布前备份数据库..."
    "$SCRIPTS_DIR/db-backup.sh" --env "$ENV_NAME" --label "pre-deploy-$RELEASE_VERSION" ||
      die "数据库备份失败，已中止部署（确认可跳过时用 --skip-backup）"
  else
    log_info "db 容器未运行，跳过发布前备份（首次部署或已 down）"
  fi
else
  log_info "跳过发布前备份"
fi

# ---------- 3. 启动 / 更新容器 ----------
log_info "启动/更新容器..."
# compose up 自身失败（镜像拉取、依赖不健康、端口占用等）在 set -e 下会直接退出，
# 这里显式接住，保证一定打印容器状态与日志，避免只剩一段英文报错。
if ! compose up -d --remove-orphans; then
  show_diagnostics
  die "容器启动失败，部署中止（见上方 compose 输出与容器日志）"
fi

# ---------- 4. 等待就绪 ----------
log_info "等待 api 健康检查通过（最长 ${WAIT_TIMEOUT}s）..."
if ! wait_for_container_health api "$WAIT_TIMEOUT"; then
  show_diagnostics
  die "api 未在 ${WAIT_TIMEOUT}s 内就绪，部署中止"
fi

log_info "等待 web 入口：$(base_url)/healthz ..."
if ! wait_for_http "$(base_url)/healthz" 60; then
  show_diagnostics
  die "web 入口不可访问，部署中止"
fi

# ---------- 5. 冒烟测试 ----------
if ((DO_SMOKE == 1)); then
  log_info "执行冒烟测试..."
  if ! "$SCRIPTS_DIR/smoke-test.sh" --env "$ENV_NAME"; then
    show_diagnostics
    rollback_target="$(state_version current || true)"
    if [[ -n "$rollback_target" && "$rollback_target" != "$RELEASE_VERSION" ]]; then
      die "冒烟测试失败。可回退到部署前的版本：
  deploy/scripts/rollback.sh --env $ENV_NAME --to $rollback_target
  （数据库备份在 $(resolve_backup_dir)）"
    fi
    die "冒烟测试失败。当前没有其他可回退版本记录（或与本次版本相同）。
  查看日志：deploy/scripts/logs.sh --env $ENV_NAME
  修复后重发：deploy/scripts/deploy.sh --env $ENV_NAME"
  fi
else
  log_info "跳过冒烟测试（--skip-smoke）"
fi

# ---------- 6. 记录发布状态 ----------
record_release "$RELEASE_VERSION"

log_ok "部署完成：$RELEASE_VERSION"
log_info "访问地址：$(base_url)"
log_info "当前版本：$(state_version current || true)"
log_info "上一版本：$(state_version previous || true)"
log_info "状态目录：$(state_dir)"
log_info "常用命令："
log_info "  查看状态  deploy/scripts/status.sh --env $ENV_NAME"
log_info "  查看日志  deploy/scripts/logs.sh --env $ENV_NAME api"
log_info "  回滚      deploy/scripts/rollback.sh --env $ENV_NAME"
compose ps
