#!/usr/bin/env bash
# 生成测试环境部署变量文件 deploy/env/<env>.env。
#
# 做什么：
#   - 从 deploy/env/staging.env.example 复制模板；
#   - 自动生成随机的 JWT_SECRET（64 位十六进制）与 POSTGRES_PASSWORD（32 位十六进制）；
#   - 把文件权限设为 600；
#   - 已存在同名 env 时默认拒绝覆盖（--force 才覆盖，会丢失旧密钥）。
#
# 用法：
#   deploy/scripts/init-env.sh                  # 生成 staging
#   deploy/scripts/init-env.sh --env staging
#   deploy/scripts/init-env.sh --env demo --force
#
# 生成后仍需人工确认：WEB_PORT、CORS_ORIGINS（测试机 IP/域名）、镜像代理（可选）。

set -euo pipefail
# env 文件含数据库密码与 JWT_SECRET：从创建时就收紧权限，避免 cp / awk 重写后变成 644。
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
FORCE=0

usage() {
  cat <<'EOF'
生成 Stellera Hub 测试环境变量文件。

用法：
  deploy/scripts/init-env.sh [--env <名称>] [--force]

参数：
  --env <名称>   环境名，默认 staging；生成 deploy/env/<名称>.env
  --force        覆盖已存在的 env 文件（会重新生成 JWT_SECRET / 数据库密码）
  -h, --help     显示帮助
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
    --force)
      FORCE=1
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

[[ "$ENV_NAME" =~ ^[A-Za-z0-9_-]+$ ]] || die "环境名不合法：${ENV_NAME}（只允许字母、数字、- 和 _）"

TEMPLATE="$DEPLOY_DIR/env/staging.env.example"
TARGET="$(env_file_for "$ENV_NAME")"

[[ -f "$TEMPLATE" ]] || die "找不到模板文件：$TEMPLATE"

if [[ -e "$TARGET" && "$FORCE" -ne 1 ]]; then
  die "环境文件已存在：$TARGET
  如需覆盖（会重新生成 JWT_SECRET 与数据库密码，旧值丢失），加 --force：
    deploy/scripts/init-env.sh --env $ENV_NAME --force"
fi

# ---------- 生成随机值 ----------
# 只生成 URL 安全的十六进制串：密码会拼进 DATABASE_URL，含 @ : / ? # 等字符会破坏解析。
gen_hex() {
  local bytes="$1"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$bytes"
    return 0
  fi
  # 退路：od 把 /dev/urandom 转成十六进制，去空白。
  head -c "$bytes" /dev/urandom | od -An -tx1 | tr -d ' \n'
}

set_env_value() {
  local key="$1" value="$2" file="$3" tmp
  tmp="${file}.tmp.$$"
  awk -v key="$key" -v value="$value" '
    BEGIN { found = 0 }
    $0 ~ ("^" key "=") { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' "$file" >"$tmp"
  mv "$tmp" "$file"
}

JWT_SECRET_VALUE="$(gen_hex 32)"
POSTGRES_PASSWORD_VALUE="$(gen_hex 16)"

HAD_EXISTING=0
if [[ -e "$TARGET" ]]; then
  HAD_EXISTING=1
fi

mkdir -p "$DEPLOY_DIR/env"
cp "$TEMPLATE" "$TARGET"
chmod 600 "$TARGET"

set_env_value "JWT_SECRET" "$JWT_SECRET_VALUE" "$TARGET"
set_env_value "POSTGRES_PASSWORD" "$POSTGRES_PASSWORD_VALUE" "$TARGET"

# 非 staging 环境：让 compose project name 与 DEPLOY_ENV 跟文件名一致，
# 避免同一台机器上多个测试环境互相覆盖容器和数据卷。
if [[ "$ENV_NAME" != "staging" ]]; then
  set_env_value "DEPLOY_ENV" "$ENV_NAME" "$TARGET"
  set_env_value "COMPOSE_PROJECT_NAME" "stellera-hub-$ENV_NAME" "$TARGET"
fi

# set_env_value 用临时文件 + mv 重写，会带上 umask 之外的新权限；这里再兜底一次 600。
chmod 600 "$TARGET"

log_ok "已生成环境文件：$TARGET"
log_info "已自动生成 JWT_SECRET（64 位十六进制）与 POSTGRES_PASSWORD（32 位十六进制），文件权限 600"
if ((HAD_EXISTING == 1)); then
  log_warn "已覆盖原有 env 文件：数据库密码已变化。"
  log_warn "如果该环境已有数据卷，PostgreSQL 里仍是旧密码，api 会连不上库。"
  log_warn "请二选一：同步修改数据库密码，或先删除数据卷重建："
  log_warn "  deploy/scripts/down.sh --env $ENV_NAME --volumes   # 会丢数据"
  log_warn "另外 --force 会用模板覆盖文件：WEB_PORT、API_PORT、CORS_ORIGINS 等自定义值也会被重置，请重新确认。"
fi
log_info "发布前请按需修改："
log_info "  - WEB_PORT / WEB_BIND：对外入口端口（默认 8080）"
log_info "  - CORS_ORIGINS：加上测试机 IP 或域名，例如 http://192.168.1.10:8080"
log_info "  - POSTGRES_IMAGE / PYTHON_IMAGE / UV_IMAGE / NODE_IMAGE / NGINX_IMAGE：内网镜像代理（可选）"
log_info "确认无误后执行：deploy/scripts/deploy.sh --env $ENV_NAME"
