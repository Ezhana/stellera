#!/usr/bin/env bash
# deploy/scripts/lib/common.sh —— 部署脚本的公共函数库。
#
# 只做这几件事，具体发布流程留在各脚本里：
#   - 定位仓库 / deploy / compose 文件路径；
#   - 加载并校验 deploy/env/<env>.env；
#   - 封装 docker compose 调用（固定 project name 与 env-file）；
#   - 计算镜像 tag、探测入口地址、等待就绪；
#   - 记录发布状态（deploy/.state/<env>/）。
#
# 用法：脚本顶部 `source "$SCRIPT_DIR/lib/common.sh"`，随后调用 init_deploy_context。
# 兼容 bash 3.2（macOS 自带）与 Linux bash，避免使用 mapfile / 关联数组等新特性。

if [[ -n "${__STELLERA_DEPLOY_COMMON__:-}" ]]; then
  return 0
fi
__STELLERA_DEPLOY_COMMON__=1

# ---------- 路径 ----------
COMMON_SH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$COMMON_SH_DIR/../.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
SCRIPTS_DIR="$DEPLOY_DIR/scripts"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose/compose.yaml}"
DEFAULT_ENV="${DEFAULT_ENV:-staging}"

# 与服务端 app/core/config.py 保持一致的示例值，用于拦截误用。
DEFAULT_INSECURE_JWT_SECRET="local-dev-only-change-me-32-characters-min"

# ---------- 输出 ----------
if [[ -t 1 ]]; then
  _C_INFO=$'\033[34m'
  _C_OK=$'\033[32m'
  _C_WARN=$'\033[33m'
  _C_ERR=$'\033[31m'
  _C_RESET=$'\033[0m'
else
  _C_INFO=''
  _C_OK=''
  _C_WARN=''
  _C_ERR=''
  _C_RESET=''
fi

log_info() { printf '%s[deploy]%s %s\n' "$_C_INFO" "$_C_RESET" "$*"; }
log_ok() { printf '%s[deploy]%s %s\n' "$_C_OK" "$_C_RESET" "$*"; }
log_warn() { printf '%s[deploy] 警告：%s%s\n' "$_C_WARN" "$*" "$_C_RESET" >&2; }
log_error() { printf '%s[deploy] 错误：%s%s\n' "$_C_ERR" "$*" "$_C_RESET" >&2; }
die() {
  log_error "$*"
  exit 1
}

# ---------- 依赖检查 ----------
require_cmd() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || die "缺少命令：$cmd"
}

require_docker() {
  require_cmd docker
  require_cmd curl
  docker info >/dev/null 2>&1 || die "无法连接 Docker daemon，请确认 Docker 已启动且当前用户有权限"
  docker compose version >/dev/null 2>&1 || die "需要 Docker Compose v2+（docker compose；v2/v5 均可）"
}

# ---------- 环境文件 ----------
# env_file_for <env>：返回 deploy/env/<env>.env 的绝对路径（不检查存在）。
env_file_for() {
  local name="$1"
  [[ "$name" =~ ^[A-Za-z0-9_-]+$ ]] || die "环境名不合法：${name}（只允许字母、数字、- 和 _）"
  printf '%s/env/%s.env\n' "$DEPLOY_DIR" "$name"
}

# load_env_file <file>：把 KEY=VALUE 载入并导出。
# env 文件由 init-env.sh 生成或人工维护，内容是我们自己的配置，因此直接用 source。
# 注意：不要在 env 文件里写命令替换或其他 shell 逻辑。
load_env_file() {
  local file="$1"
  [[ -f "$file" ]] || die "找不到环境文件：$file
  首次部署请先运行：deploy/scripts/init-env.sh --env $(basename "$file" .env)
  或手工复制模板：cp deploy/env/staging.env.example $file && chmod 600 $file"
  # shellcheck disable=SC1090
  set -a
  . "$file"
  set +a
}

# init_deploy_context <env>：加载 env 文件并统一导出部署上下文变量。
# 调用后可用：ENV_NAME / ENV_FILE / DEPLOY_ENV / COMPOSE_PROJECT_NAME，以及 env 文件中的所有变量。
init_deploy_context() {
  ENV_NAME="$1"
  ENV_FILE="$(env_file_for "$ENV_NAME")"
  export ENV_NAME ENV_FILE
  load_env_file "$ENV_FILE"
  DEPLOY_ENV="$ENV_NAME"
  COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-stellera-hub-$DEPLOY_ENV}"
  export DEPLOY_ENV COMPOSE_PROJECT_NAME
}

# ---------- 变量校验 ----------
require_var() {
  local name="$1"
  [[ -n "${!name:-}" ]] || die "环境变量 $name 未设置（$(basename "${ENV_FILE:-env}")）"
}

# validate_deploy_env：发布前的最低限校验。故意不校验弱口令演示账号——测试环境
# 明确保留它们；只对 production 做硬性拦截。
validate_deploy_env() {
  local app_env="${APP_ENV:-staging}"
  local seed_demo="${SEED_DEMO_USERS:-false}"

  require_var POSTGRES_USER
  require_var POSTGRES_PASSWORD
  require_var POSTGRES_DB
  require_var WEB_PORT
  require_var JWT_SECRET
  require_var CORS_ORIGINS

  [[ "$POSTGRES_PASSWORD" != replace-* ]] || die "POSTGRES_PASSWORD 还是模板占位值，请运行 init-env.sh 或手工改成强密码"
  [[ "$JWT_SECRET" != replace-* ]] || die "JWT_SECRET 还是模板占位值，请运行 init-env.sh 或手工生成（openssl rand -hex 32）"
  [[ "$JWT_SECRET" != "$DEFAULT_INSECURE_JWT_SECRET" ]] || die "JWT_SECRET 使用了本地开发示例值，非 development 环境必须更换"
  (( ${#JWT_SECRET} >= 32 )) || die "JWT_SECRET 至少需要 32 个字符（当前 ${#JWT_SECRET}）"
  [[ "$WEB_PORT" =~ ^[0-9]+$ ]] || die "WEB_PORT 必须是数字：$WEB_PORT"
  [[ -n "${API_PORT:-}" && "${API_PORT}" =~ ^[0-9]+$ ]] || die "API_PORT 必须是数字：${API_PORT:-<未设置>}"

  if [[ "$app_env" == "production" ]]; then
    [[ "$seed_demo" != "true" ]] || die "生产环境不允许 SEED_DEMO_USERS=true（会创建弱口令演示账号）"
    local var
    for var in SEED_ADMIN_PASSWORD SEED_OPERATOR_PASSWORD SEED_VIEWER_PASSWORD \
      SEED_ENTERPRISE_PASSWORD SEED_ENGINEER_PASSWORD; do
      case "${!var:-}" in
        admin12345 | enterprise12345 | engineer12345 | operator12345 | viewer12345)
          die "生产环境仍在使用演示弱口令：$var=${!var}"
          ;;
      esac
    done
  elif [[ "$app_env" == "staging" && "$seed_demo" == "true" ]]; then
    log_warn "测试环境启用了弱口令演示账号与演示订单（SEED_DEMO_USERS=true），仅限内网测试使用"
  fi

  case "$app_env" in
    development | test | staging | production) ;;
    *) die "APP_ENV 取值不合法：${app_env}（应为 development/test/staging/production）" ;;
  esac

  [[ -f "$COMPOSE_FILE" ]] || die "找不到 compose 文件：$COMPOSE_FILE"
}

# ---------- 版本与镜像 ----------
# resolve_release_version：取 git describe（含 -dirty）作为发布版本；不在 git 仓库时用时间戳。
resolve_release_version() {
  local described
  if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    described="$(git -C "$REPO_ROOT" describe --tags --always --dirty 2>/dev/null || true)"
    if [[ -n "$described" ]]; then
      # docker tag 不允许 / 与 +，统一替换为 -。
      printf '%s\n' "${described//\//-}"
      return 0
    fi
  fi
  date '+%Y%m%d-%H%M%S'
}

# current_release_version：从 api 容器实际使用的镜像名解析当前发布版本（含已停止容器），
# 没有容器时回退到状态文件 current。用于 db-restore.sh 这类不经过 deploy.sh 的地方，
# 避免 compose 因缺少 RELEASE_VERSION 而回落到 :local 触发意外构建。
current_release_version() {
  local cid image
  cid="$(compose ps -q -a api 2>/dev/null || true)"
  if [[ -n "$cid" ]]; then
    image="$(docker inspect --format '{{.Config.Image}}' "$cid" 2>/dev/null || true)"
    if [[ -n "$image" ]]; then
      printf '%s\n' "${image##*:}"
      return 0
    fi
  fi
  state_version current
}

# image_ref <api|web>：与 compose.yaml 里的 image 表达式保持一致。
image_ref() {
  local component="$1"
  printf '%s-hub-%s:%s\n' "${IMAGE_PREFIX:-stellera}" "$component" "${RELEASE_VERSION:?RELEASE_VERSION 未设置}"
}

# ---------- compose 封装 ----------
# 固定 --project-name 与 --env-file，避免不同 env 互相覆盖或读错工作目录下的 .env。
compose() {
  docker compose \
    --project-name "${COMPOSE_PROJECT_NAME:?COMPOSE_PROJECT_NAME 未设置}" \
    --env-file "${ENV_FILE:?ENV_FILE 未设置}" \
    -f "$COMPOSE_FILE" \
    "$@"
}

# ---------- 访问地址 ----------
# 探活从部署机本机发起：WEB_BIND 是 0.0.0.0/:: 时走 127.0.0.1，否则用绑定地址。
probe_host() {
  case "${WEB_BIND:-0.0.0.0}" in
    0.0.0.0 | "::" | "") printf '127.0.0.1\n' ;;
    *) printf '%s\n' "$WEB_BIND" ;;
  esac
}

base_url() {
  printf 'http://%s:%s\n' "$(probe_host)" "${WEB_PORT:-8080}"
}

# API 探活地址：API_BIND 是 0.0.0.0/:: 时走 127.0.0.1，否则用绑定地址。
api_probe_host() {
  case "${API_BIND:-127.0.0.1}" in
    0.0.0.0 | "::" | "") printf '127.0.0.1\n' ;;
    *) printf '%s\n' "$API_BIND" ;;
  esac
}

api_base_url() {
  printf 'http://%s:%s\n' "$(api_probe_host)" "${API_PORT:-8000}"
}

# ---------- 就绪等待 ----------
# wait_for_http <url> <timeout_seconds>：轮询 URL 直到 2xx；超时返回 1。
wait_for_http() {
  local url="$1" timeout="${2:-60}" deadline=$((SECONDS + ${2:-60}))
  while ((SECONDS < deadline)); do
    if curl -fsS --max-time 3 -o /dev/null "$url" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

# wait_for_container_health <service> <timeout_seconds>：等待 compose 服务的 healthcheck 变 healthy。
wait_for_container_health() {
  local service="$1" timeout="${2:-180}" deadline=$((SECONDS + ${2:-180}))
  local cid="" status=""
  while ((SECONDS < deadline)); do
    cid="$(compose ps -q "$service" 2>/dev/null || true)"
    if [[ -n "$cid" ]]; then
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid" 2>/dev/null || true)"
      if [[ "$status" == "healthy" ]]; then
        return 0
      fi
      if [[ "$status" == "unhealthy" ]]; then
        return 1
      fi
    fi
    sleep 2
  done
  return 1
}

# ---------- 发布状态 ----------
state_dir() {
  printf '%s/.state/%s\n' "$DEPLOY_DIR" "${DEPLOY_ENV:-${ENV_NAME:-staging}}"
}

# state_version <current|previous>：读取状态文件第一列（版本号），文件不存在时输出空。
state_version() {
  local kind="$1" file
  file="$(state_dir)/$kind"
  if [[ -f "$file" ]]; then
    cut -f1 "$file" | head -n 1
  fi
}

# record_release <version>：部署成功后写入 current，并把旧 current 存为 previous。
record_release() {
  local version="$1" dir now old_current=""
  dir="$(state_dir)"
  mkdir -p "$dir"
  now="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  if [[ -f "$dir/current" ]]; then
    old_current="$(cut -f1 "$dir/current" | head -n 1)"
  fi
  if [[ -n "$old_current" && "$old_current" != "$version" ]]; then
    cp "$dir/current" "$dir/previous"
  fi
  printf '%s\t%s\n' "$version" "$now" >"$dir/current"
  printf '%s\t%s\t%s\n' "$now" "$version" "deploy" >>"$dir/history.log"
}

# swap_release_state <version> <action>：回滚后更新 current/previous，保持可来回切换。
swap_release_state() {
  local version="$1" action="${2:-rollback}" dir now old_current=""
  dir="$(state_dir)"
  mkdir -p "$dir"
  now="$(date '+%Y-%m-%dT%H:%M:%S%z')"
  if [[ -f "$dir/current" ]]; then
    old_current="$(cut -f1 "$dir/current" | head -n 1)"
  fi
  if [[ -n "$old_current" && "$old_current" != "$version" ]]; then
    printf '%s\t%s\n' "$old_current" "$now" >"$dir/previous"
  fi
  printf '%s\t%s\n' "$version" "$now" >"$dir/current"
  printf '%s\t%s\t%s\n' "$now" "$version" "$action" >>"$dir/history.log"
}

# resolve_backup_dir：BACKUP_DIR 相对 deploy/ 解析，绝对路径原样返回。
resolve_backup_dir() {
  local dir="${BACKUP_DIR:-.state/backups}"
  case "$dir" in
    /*) printf '%s\n' "$dir" ;;
    *) printf '%s/%s\n' "$DEPLOY_DIR" "$dir" ;;
  esac
}

# human_size <bytes>：把字节数转成便于阅读的大小。
human_size() {
  local bytes="$1"
  if ((bytes >= 1048576)); then
    printf '%s MiB\n' "$(awk -v b="$bytes" 'BEGIN { printf "%.1f", b / 1048576 }')"
  elif ((bytes >= 1024)); then
    printf '%s KiB\n' "$(awk -v b="$bytes" 'BEGIN { printf "%.1f", b / 1024 }')"
  elif ((bytes >= 0)); then
    printf '%s B\n' "$bytes"
  else
    printf '未知\n'
  fi
}

# require_answer <expected> <prompt>：危险操作前的交互确认；非交互环境直接报错。
require_answer() {
  local expected="$1" prompt="$2" answer=""
  if [[ ! -t 0 ]]; then
    die "${prompt}（非交互环境请显式传 --yes）"
  fi
  printf '%s' "$prompt" >&2
  read -r answer
  [[ "$answer" == "$expected" ]] || die "已取消（需要输入 $expected 确认）"
}
