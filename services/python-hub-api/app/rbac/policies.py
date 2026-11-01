"""不需要登录即可访问的公开策略。

这些策略不属于任何数据库角色（匿名主体不是用户），所以放在代码里；
角色权限仍然以 PostgreSQL 为唯一事实来源。
"""

from __future__ import annotations

# (subject, object, action)
PUBLIC_POLICIES: tuple[tuple[str, str, str], ...] = (
    ("anonymous", "/health", "GET"),
    ("anonymous", "/health/ready", "GET"),
    ("anonymous", "/api/v1/auth/login", "POST"),
    ("anonymous", "/api/v1/auth/token", "POST"),
    ("anonymous", "/api/v1/auth/refresh", "POST"),
    ("anonymous", "/docs", "GET"),
    ("anonymous", "/docs/oauth2-redirect", "GET"),
    ("anonymous", "/redoc", "GET"),
    ("anonymous", "/openapi.json", "GET"),
)
