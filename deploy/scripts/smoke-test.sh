#!/usr/bin/env bash
# 测试环境冒烟测试：验证「入口 -> nginx -> api -> 数据库 -> RBAC」整条链路。
#
# 检查项：
#   1. web /healthz 返回 200；
#   2. 首页与 /login 返回 200（SPA 入口可用）；
#   3. POST /api/v1/auth/login 能用 admin 账号登录；
#   4. 带 token 访问 /api/v1/auth/me 与 /api/v1/fde/orders；
#   5. 未带 token 访问订单接口返回 401（RBAC 中间件生效）；
#   6. WebSocket /api/v1/fde/ws 握手返回 101（实时推送通道可用）。
#
# 用法：
#   deploy/scripts/smoke-test.sh --env staging
#   deploy/scripts/smoke-test.sh --base-url http://127.0.0.1:18080 --username admin --password admin12345
#
# 参数：
#   --env <名称>        环境名，默认 staging（用于读取入口地址与登录账号）
#   --base-url <URL>    直接指定入口地址（给了就不再读 env 文件）
#   --username <用户>   登录账号，默认取 SEED_ADMIN_USERNAME
#   --password <密码>   登录密码，默认取 SEED_ADMIN_PASSWORD
#   --skip-ws           跳过 WebSocket 握手检查

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
. "$SCRIPT_DIR/lib/common.sh"

ENV_NAME="$DEFAULT_ENV"
BASE_URL=""
USERNAME=""
PASSWORD=""
SKIP_WS=0

PASS=0
FAIL=0
WARN=0

usage() {
  cat <<'EOF'
Stellera Hub 测试环境冒烟测试。

用法：
  deploy/scripts/smoke-test.sh [--env <名称>] [--base-url <URL>] [--username <用户>] [--password <密码>] [--skip-ws]

参数：
  --env <名称>        环境名，默认 staging
  --base-url <URL>    直接指定入口地址（如 http://127.0.0.1:18080）
  --username <用户>   登录账号，默认取 env 里的 SEED_ADMIN_USERNAME
  --password <密码>   登录密码，默认取 env 里的 SEED_ADMIN_PASSWORD
  --skip-ws           跳过 WebSocket 握手检查
  -h, --help          显示帮助
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
    --base-url)
      [[ $# -ge 2 ]] || die "--base-url 需要一个参数"
      BASE_URL="$2"
      shift 2
      ;;
    --base-url=*)
      BASE_URL="${1#*=}"
      shift
      ;;
    --username)
      [[ $# -ge 2 ]] || die "--username 需要一个参数"
      USERNAME="$2"
      shift 2
      ;;
    --username=*)
      USERNAME="${1#*=}"
      shift
      ;;
    --password)
      [[ $# -ge 2 ]] || die "--password 需要一个参数"
      PASSWORD="$2"
      shift 2
      ;;
    --password=*)
      PASSWORD="${1#*=}"
      shift
      ;;
    --skip-ws)
      SKIP_WS=1
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

require_cmd curl

if [[ -z "$BASE_URL" ]]; then
  init_deploy_context "$ENV_NAME"
  BASE_URL="$(base_url)"
  USERNAME="${USERNAME:-${SEED_ADMIN_USERNAME:-admin}}"
  PASSWORD="${PASSWORD:-${SEED_ADMIN_PASSWORD:-admin12345}}"
else
  USERNAME="${USERNAME:-admin}"
  PASSWORD="${PASSWORD:-admin12345}"
fi
BASE_URL="${BASE_URL%/}"

check_ok() {
  PASS=$((PASS + 1))
  printf '  [OK]   %s\n' "$1"
}

check_fail() {
  FAIL=$((FAIL + 1))
  printf '  [FAIL] %s\n' "$1"
}

check_warn() {
  WARN=$((WARN + 1))
  printf '  [WARN] %s\n' "$1"
}

http_code() {
  curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "$@" 2>/dev/null || true
}

http_body() {
  curl -sS --max-time 10 "$@" 2>/dev/null || true
}

# 从单行 JSON 里取字符串字段：优先 python3，退路 sed（避免依赖 jq）。
extract_json_string() {
  local body="$1" key="$2" value=""
  if command -v python3 >/dev/null 2>&1; then
    value="$(printf '%s' "$body" | python3 -c 'import json,sys
try:
    print(json.load(sys.stdin).get(sys.argv[1], "") or "")
except Exception:
    print("")' "$key" 2>/dev/null || true)"
  fi
  if [[ -z "$value" ]]; then
    value="$(printf '%s' "$body" | sed -n "s/.*\"$key\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1)"
  fi
  printf '%s\n' "$value"
}

printf '冒烟测试入口：%s\n' "$BASE_URL"

# ---------- 1. web 健康检查 ----------
code="$(http_code "$BASE_URL/healthz")"
if [[ "$code" == "200" ]]; then
  check_ok "web /healthz 返回 200"
else
  check_fail "web /healthz 返回 ${code}（期望 200）"
fi

# ---------- 2. SPA 入口 ----------
code="$(http_code "$BASE_URL/")"
body="$(http_body "$BASE_URL/")"
if [[ "$code" == "200" && "$body" == *'id="app"'* ]]; then
  check_ok "首页返回 200 且包含 SPA 挂载点"
else
  check_fail "首页异常（HTTP ${code}，SPA 挂载点缺失）"
fi

code="$(http_code "$BASE_URL/login")"
if [[ "$code" == "200" ]]; then
  check_ok "/login 返回 200（history 回退正常）"
else
  check_fail "/login 返回 ${code}（期望 200）"
fi

# ---------- 3. 登录 ----------
login_resp="$(curl -sS --max-time 10 -X POST "$BASE_URL/api/v1/auth/login" \
  -H 'Content-Type: application/json' \
  --data "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" \
  -w $'\n%{http_code}' 2>/dev/null || true)"
login_code="${login_resp##*$'\n'}"
login_body="${login_resp%$'\n'*}"

if [[ "$login_code" == "200" ]]; then
  check_ok "admin 账号登录成功（/api/v1/auth/login）"
else
  check_fail "登录失败（HTTP ${login_code}，账号 ${USERNAME}）"
fi

TOKEN="$(extract_json_string "$login_body" access_token)"
if [[ -n "$TOKEN" ]]; then
  check_ok "登录响应包含 access_token"
else
  check_fail "登录响应缺少 access_token"
fi

# ---------- 4. 带 token 的受保护接口 ----------
if [[ -n "$TOKEN" ]]; then
  auth_header="Authorization: Bearer $TOKEN"

  code="$(http_code -H "$auth_header" "$BASE_URL/api/v1/auth/me")"
  body="$(http_body -H "$auth_header" "$BASE_URL/api/v1/auth/me")"
  if [[ "$code" == "200" && "$body" == *'"username"'* ]]; then
    check_ok "带 token 访问 /api/v1/auth/me 成功"
  else
    check_fail "带 token 访问 /api/v1/auth/me 失败（HTTP ${code}）"
  fi

  code="$(http_code -H "$auth_header" "$BASE_URL/api/v1/fde/orders")"
  body="$(http_body -H "$auth_header" "$BASE_URL/api/v1/fde/orders")"
  if [[ "$code" == "200" && "$body" == *'"items"'* && "$body" == *'"total"'* ]]; then
    check_ok "带 token 拉取订单大厅成功（items/total 结构正常）"
  else
    check_fail "带 token 拉取订单大厅失败（HTTP ${code}）"
  fi

  # 演示订单为软检查：测试环境数据被清理过时不算发布失败。
  demo_resp="$(http_body -H "$auth_header" "$BASE_URL/api/v1/fde/orders?page_size=100")"
  if [[ -n "$demo_resp" ]] && printf '%s' "$demo_resp" | grep -q 'FDE-DEMO-'; then
    check_ok "演示订单存在（FDE-DEMO-*）"
  else
    check_warn "未在第一页看到演示订单（可能数据已清理，或已超过 100 条）"
  fi
else
  check_fail "无 token，跳过受保护接口检查"
fi

# ---------- 5. 未认证访问应返回 401 ----------
code="$(http_code "$BASE_URL/api/v1/fde/orders")"
if [[ "$code" == "401" ]]; then
  check_ok "未认证访问订单接口返回 401（RBAC 生效）"
else
  check_fail "未认证访问订单接口返回 ${code}（期望 401）"
fi

# ---------- 6. WebSocket 握手 ----------
if ((SKIP_WS == 0)); then
  # 不带 token：服务端会先完成握手再以 4401 关闭，因此这里只验证 nginx 的 upgrade 通路。
  # curl 会因为在等连接关闭而超时，所以只用 -w 取状态码并忽略退出码。
  ws_code="$(curl -sS --http1.1 --max-time 3 -o /dev/null -w '%{http_code}' \
    -H 'Connection: Upgrade' \
    -H 'Upgrade: websocket' \
    -H 'Sec-WebSocket-Version: 13' \
    -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
    "$BASE_URL/api/v1/fde/ws" 2>/dev/null || true)"
  if [[ "$ws_code" == "101" ]]; then
    check_ok "WebSocket /api/v1/fde/ws 握手返回 101"
  else
    check_fail "WebSocket 握手返回 ${ws_code}（期望 101，检查 nginx upgrade 配置）"
  fi
fi

# ---------- 总结 ----------
printf '\n冒烟测试结果：通过 %d 项，失败 %d 项，警告 %d 项\n' "$PASS" "$FAIL" "$WARN"
if ((FAIL > 0)); then
  exit 1
fi
