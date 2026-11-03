"""JWT 认证：把 Bearer token 解析成 Starlette 的 scope["user"]。

只做令牌校验（不查数据库）；需要完整用户信息时由端点通过 session 读取。
令牌无效时返回 None，由 AuthenticationMiddleware 置为 UnauthenticatedUser，
再由 CasbinRBACMiddleware 决定 401 还是 403。
"""

from __future__ import annotations

from dataclasses import dataclass

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    BaseUser,
)
from starlette.requests import HTTPConnection

from app.security.tokens import TokenError, TokenService


@dataclass(frozen=True)
class UserPrincipal(BaseUser):
    user_id: int

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return f"user:{self.user_id}"

    @property
    def identity(self) -> str:
        return str(self.user_id)


class JWTAuthBackend(AuthenticationBackend):
    def __init__(self, token_service: TokenService) -> None:
        self._tokens = token_service

    async def authenticate(
        self, conn: HTTPConnection
    ) -> tuple[AuthCredentials, UserPrincipal] | None:
        authorization = conn.headers.get("Authorization")
        if not authorization:
            return None
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return None
        try:
            claims = self._tokens.decode_access_token(token.strip())
        except TokenError:
            return None
        return AuthCredentials(["authenticated"]), UserPrincipal(user_id=claims.user_id)
