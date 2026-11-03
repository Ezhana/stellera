"""Casbin 守卫中间件。

等价于 fastapi-casbin-auth 的核心逻辑，但补上了：
- 路径归一化（防 `//`、尾斜杠绕过）；
- 未认证 401 / 已认证但无权限 403 的区分；
- OPTIONS 直接放行（预检请求交给 CORS 处理）。

公开路径先按 `anonymous` 主体检查，命中即放行——这样已登录用户也能调用
/login、/health 这类公开端点。
"""

from __future__ import annotations

import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.middleware.authentication import UserPrincipal
from app.rbac.enforcer import ANONYMOUS_SUBJECT, EnforcerGuard, user_subject

_MULTI_SLASH_RE = re.compile(r"/{2,}")


def normalize_path(path: str) -> str:
    """把 `//api//v1//auth/me/` 归一成 `/api/v1/auth/me`，仅用于权限判断。"""
    if not path.startswith("/"):
        path = f"/{path}"
    path = _MULTI_SLASH_RE.sub("/", path)
    if len(path) > 1:
        path = path.rstrip("/") or "/"
    return path


def _json_response(
    status_code: int, detail: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status_code, headers=headers)


class CasbinRBACMiddleware:
    """纯 ASGI 中间件：不依赖具体框架，enforcer 从 app.state 取。"""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope["method"].upper()
        if method != "OPTIONS":
            guard: EnforcerGuard | None = getattr(scope["app"].state, "enforcer_guard", None)
            if guard is None:
                response = _json_response(503, "RBAC not ready")
                await response(scope, receive, send)
                return

            path = normalize_path(scope.get("path", "/"))
            principal = scope.get("user")
            authenticated = isinstance(principal, UserPrincipal)
            subject = user_subject(principal.user_id) if authenticated else ANONYMOUS_SUBJECT

            allowed = guard.enforce(ANONYMOUS_SUBJECT, path, method) or guard.enforce(
                subject, path, method
            )
            if not allowed:
                if authenticated:
                    response = _json_response(403, "Forbidden")
                else:
                    response = _json_response(
                        401,
                        "Not authenticated",
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
