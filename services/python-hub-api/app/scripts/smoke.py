"""镜像内冒烟测试：验证「入口 -> web -> api -> 数据库 -> RBAC」整条链路。

只依赖 Python 标准库，由 entrypoint.sh 的 smoke 子命令触发，在 compose 网络内运行：
    docker compose run --rm smoke

环境变量：
    SMOKE_BASE_URL  入口地址，默认 http://web（compose 服务名）
    SMOKE_USERNAME  登录账号，默认 admin
    SMOKE_PASSWORD  登录密码，默认 admin12345

检查项（覆盖「入口 -> nginx -> api -> 数据库 -> RBAC」全链路）：
    1. web /healthz 返回 200；
    2. 首页返回 200 且包含 SPA 挂载点 id="app"；
    3. /login 返回 200（history 回退正常）；
    4. POST /api/v1/auth/login 200 且响应包含 access_token；
    5. 带 token GET /api/v1/auth/me 200 且包含 username；
    6. 带 token GET /api/v1/fde/orders 200 且包含 items/total；
    7. 未带 token GET /api/v1/fde/orders 返回 401（RBAC 生效）；
    8. WebSocket /api/v1/fde/ws 握手返回 101（实时推送通道可用）。

任一检查失败时进程以 1 退出，便于 CI/发布脚本判定。
"""

from __future__ import annotations

import http.client
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit

DEFAULT_BASE_URL = "http://web"
DEFAULT_USERNAME = "admin"
DEFAULT_PASSWORD = "admin12345"
REQUEST_TIMEOUT_SECONDS = 10

# WebSocket 握手固定的示例 key（RFC 6455 示例值，不需要真随机）。
WS_SAMPLE_KEY = "dGhlIHNhbXBsZSBub25jZQ=="
API_PREFIX = "/api/v1"


@dataclass(frozen=True)
class Target:
    """解析后的入口地址；base_path 支持入口挂在子路径下的情况。"""

    scheme: str
    host: str
    port: int
    base_path: str = ""

    def path(self, suffix: str) -> str:
        return f"{self.base_path}{suffix}"


@dataclass(frozen=True)
class Response:
    status: int
    body: bytes


class Runner:
    """统计并打印 [OK] / [FAIL]。"""

    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def ok(self, message: str) -> None:
        self.passed += 1
        print(f"  [OK]   {message}")

    def fail(self, message: str) -> None:
        self.failed += 1
        print(f"  [FAIL] {message}")


def parse_base_url(raw: str) -> Target:
    candidate = raw.strip() or DEFAULT_BASE_URL
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise SystemExit(f"[FAIL] SMOKE_BASE_URL 不合法：{candidate}（示例：http://web）")
    port = parts.port or (443 if parts.scheme == "https" else 80)
    return Target(
        scheme=parts.scheme,
        host=parts.hostname,
        port=port,
        base_path=parts.path.rstrip("/"),
    )


def _connect(target: Target) -> http.client.HTTPConnection:
    if target.scheme == "https":
        return http.client.HTTPSConnection(
            target.host, target.port, timeout=REQUEST_TIMEOUT_SECONDS
        )
    return http.client.HTTPConnection(target.host, target.port, timeout=REQUEST_TIMEOUT_SECONDS)


def request(
    target: Target,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> Response:
    """发一个请求并读完响应体；连接失败/超时抛 OSError/HTTPException 由调用方兜底。"""
    connection = _connect(target)
    try:
        connection.request(method, target.path(path), body=body, headers=headers or {})
        raw = connection.getresponse()
        return Response(status=raw.status, body=raw.read())
    finally:
        connection.close()


def websocket_status(target: Target, path: str) -> int:
    """手动发 WebSocket Upgrade 头，只取握手状态码（不能读 101 之后的帧）。"""
    connection = _connect(target)
    try:
        connection.putrequest("GET", target.path(path))
        connection.putheader("Connection", "Upgrade")
        connection.putheader("Upgrade", "websocket")
        connection.putheader("Sec-WebSocket-Version", "13")
        connection.putheader("Sec-WebSocket-Key", WS_SAMPLE_KEY)
        connection.endheaders()
        response = connection.getresponse()
        return response.status
    finally:
        connection.close()


def _json_object(body: bytes) -> dict[str, object]:
    try:
        decoded: object = json.loads(body)
    except json.JSONDecodeError:
        return {}
    if isinstance(decoded, dict):
        return {str(key): value for key, value in decoded.items()}
    return {}


def main() -> int:
    base_url = os.environ.get("SMOKE_BASE_URL", DEFAULT_BASE_URL)
    username = os.environ.get("SMOKE_USERNAME", DEFAULT_USERNAME)
    password = os.environ.get("SMOKE_PASSWORD", DEFAULT_PASSWORD)

    target = parse_base_url(base_url)
    runner = Runner()
    print(f"[smoke] 冒烟测试入口：{base_url}（账号 {username}）")

    token = ""

    def check_healthz() -> None:
        response = request(target, "GET", "/healthz")
        if response.status == 200:
            runner.ok("web /healthz 返回 200")
        else:
            runner.fail(f"web /healthz 返回 {response.status}（期望 200）")

    def check_index() -> None:
        response = request(target, "GET", "/")
        body = response.body
        if response.status == 200 and b'id="app"' in body:
            runner.ok("首页返回 200 且包含 SPA 挂载点")
        elif response.status != 200:
            runner.fail(f"首页返回 {response.status}（期望 200）")
        else:
            runner.fail('首页返回 200 但缺少 SPA 挂载点 id="app"')

    def check_login_page() -> None:
        response = request(target, "GET", "/login")
        if response.status == 200:
            runner.ok("/login 返回 200（history 回退正常）")
        else:
            runner.fail(f"/login 返回 {response.status}（期望 200）")

    def check_login() -> None:
        nonlocal token
        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        response = request(
            target,
            "POST",
            f"{API_PREFIX}/auth/login",
            headers={"Content-Type": "application/json"},
            body=payload,
        )
        if response.status != 200:
            runner.fail(f"登录失败：/api/v1/auth/login 返回 {response.status}（账号 {username}）")
            return
        token = str(_json_object(response.body).get("access_token") or "")
        if token:
            runner.ok("admin 账号登录成功且响应包含 access_token")
        else:
            runner.fail("登录成功但响应缺少 access_token")

    def check_me() -> None:
        if not token:
            runner.fail("带 token 访问 /api/v1/auth/me：缺少 access_token")
            return
        response = request(
            target,
            "GET",
            f"{API_PREFIX}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status != 200:
            runner.fail(f"带 token 访问 /api/v1/auth/me 返回 {response.status}（期望 200）")
        elif b'"username"' not in response.body:
            runner.fail("带 token 访问 /api/v1/auth/me 响应缺少 username")
        else:
            runner.ok("带 token 访问 /api/v1/auth/me 成功且包含 username")

    def check_orders() -> None:
        if not token:
            runner.fail("带 token 访问 /api/v1/fde/orders：缺少 access_token")
            return
        response = request(
            target,
            "GET",
            f"{API_PREFIX}/fde/orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status != 200:
            runner.fail(f"带 token 拉取订单大厅返回 {response.status}（期望 200）")
        elif b'"items"' not in response.body or b'"total"' not in response.body:
            runner.fail("带 token 拉取订单大厅响应缺少 items/total 结构")
        else:
            runner.ok("带 token 拉取订单大厅成功（items/total 结构正常）")

    def check_unauthorized_orders() -> None:
        response = request(target, "GET", f"{API_PREFIX}/fde/orders")
        if response.status == 401:
            runner.ok("未认证访问订单接口返回 401（RBAC 生效）")
        else:
            runner.fail(f"未认证访问订单接口返回 {response.status}（期望 401）")

    def check_websocket() -> None:
        status = websocket_status(target, f"{API_PREFIX}/fde/ws")
        if status == 101:
            runner.ok("WebSocket /api/v1/fde/ws 握手返回 101（实时通道可用）")
        else:
            runner.fail(f"WebSocket /api/v1/fde/ws 握手返回 {status}（期望 101）")

    checks: list[tuple[str, Callable[[], None]]] = [
        ("GET /healthz", check_healthz),
        ("GET /", check_index),
        ("GET /login", check_login_page),
        ("POST /api/v1/auth/login", check_login),
        ("GET /api/v1/auth/me", check_me),
        ("GET /api/v1/fde/orders（带 token）", check_orders),
        ("GET /api/v1/fde/orders（匿名）", check_unauthorized_orders),
        ("WebSocket /api/v1/fde/ws", check_websocket),
    ]

    for label, check in checks:
        try:
            check()
        except (OSError, http.client.HTTPException) as exc:
            runner.fail(f"{label} 请求异常：{type(exc).__name__}: {exc}")

    print()
    print(f"[smoke] 结果：通过 {runner.passed} 项，失败 {runner.failed} 项")
    return 1 if runner.failed else 0


if __name__ == "__main__":
    sys.exit(main())
