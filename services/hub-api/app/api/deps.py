"""FastAPI 依赖：数据库会话、当前用户、认证服务与 RBAC 守卫。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.middleware.authentication import UserPrincipal
from app.rbac.enforcer import EnforcerGuard
from app.services.auth import AuthService

# 仅用于 OpenAPI/Swagger 的 Authorize 对话框；实际令牌校验由 JWTAuthBackend 完成。
# auto_error=False：缺失令牌时交给 Casbin 中间件决定 401/403，而不是在这里提前报错。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_current_user(
    request: Request,
    _token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> UserPrincipal:
    """Casbin 中间件已经拦过未认证请求；这里再做一次端点级兜底。

    `_token` 只为让 OpenAPI 声明 OAuth2 password flow（Swagger 的 Authorize 按钮）；
    真正的 Bearer 解析在 `JWTAuthBackend`。
    """
    principal = request.scope.get("user")
    if not isinstance(principal, UserPrincipal):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


CurrentUserDep = Annotated[UserPrincipal, Depends(get_current_user)]


def get_enforcer_guard(request: Request) -> EnforcerGuard:
    guard = getattr(request.app.state, "enforcer_guard", None)
    if guard is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="RBAC not ready"
        )
    return guard


def get_auth_service(request: Request) -> AuthService:
    return AuthService(
        settings=request.app.state.settings,
        token_service=request.app.state.token_service,
        guard=get_enforcer_guard(request),
    )
