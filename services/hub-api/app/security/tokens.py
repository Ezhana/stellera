"""JWT 签发与校验。

注意：Authlib 1.9 已把 `authlib.jose` 标记为 deprecated（1.x 内保持兼容，建议
迁移 joserfc）。这里把所有 JOSE 调用集中在一个类里，未来迁移只需改本文件。

令牌约定：
- HS256，claims 含 iss / aud / sub / iat / nbf / exp / jti / typ；
- access 与 refresh 用 `typ` 区分，校验时强制匹配，避免拿 refresh 当 access 用；
- refresh token 的 jti 入库，库里只保存 SHA-256 摘要（见 app/models/refresh_token.py）。
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from authlib.jose import jwt
from authlib.jose.errors import JoseError

from app.core.config import Settings

TokenType = Literal["access", "refresh"]

ACCESS_TOKEN_TYPE: TokenType = "access"
REFRESH_TOKEN_TYPE: TokenType = "refresh"


class TokenError(Exception):
    """令牌无效的基类；上层统一转成 HTTP 401。"""


class InvalidTokenError(TokenError):
    pass


class ExpiredTokenError(TokenError):
    pass


class WrongTokenTypeError(TokenError):
    pass


@dataclass(frozen=True)
class IssuedToken:
    token: str
    jti: str
    token_hash: str
    issued_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    jti: str
    token_type: TokenType
    issued_at: datetime
    expires_at: datetime


def hash_token(token: str) -> str:
    """refresh token 入库前做 SHA-256（令牌本身不落库）。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenService:
    def __init__(self, settings: Settings) -> None:
        self._secret = settings.jwt_secret
        self._issuer = settings.jwt_issuer
        self._audience = settings.jwt_audience
        self._access_ttl = timedelta(seconds=settings.access_token_ttl_seconds)
        self._refresh_ttl = timedelta(seconds=settings.refresh_token_ttl_seconds)

    # ---------- 对外 API ----------
    def create_access_token(self, user_id: int) -> IssuedToken:
        return self._create_token(user_id, ACCESS_TOKEN_TYPE, self._access_ttl)

    def create_refresh_token(self, user_id: int) -> IssuedToken:
        return self._create_token(user_id, REFRESH_TOKEN_TYPE, self._refresh_ttl)

    def decode_access_token(self, token: str) -> TokenClaims:
        return self._decode_token(token, expected_type=ACCESS_TOKEN_TYPE)

    def decode_refresh_token(self, token: str) -> TokenClaims:
        return self._decode_token(token, expected_type=REFRESH_TOKEN_TYPE)

    # ---------- 内部实现 ----------
    def _create_token(self, user_id: int, token_type: TokenType, ttl: timedelta) -> IssuedToken:
        now = datetime.now(UTC)
        expires_at = now + ttl
        jti = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "iss": self._issuer,
            "aud": self._audience,
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": jti,
            "typ": token_type,
        }
        encoded = jwt.encode({"alg": "HS256"}, payload, self._secret)
        token = encoded.decode("utf-8") if isinstance(encoded, bytes) else str(encoded)
        return IssuedToken(
            token=token,
            jti=jti,
            token_hash=hash_token(token),
            issued_at=now,
            expires_at=expires_at,
        )

    def _decode_token(self, token: str, expected_type: TokenType) -> TokenClaims:
        claims_options: dict[str, dict[str, Any]] = {
            "iss": {"essential": True, "value": self._issuer},
            "aud": {"essential": True, "value": self._audience},
            "sub": {"essential": True},
            "exp": {"essential": True},
            "iat": {"essential": True},
        }
        try:
            claims = jwt.decode(token, self._secret, claims_options=claims_options)
            claims.validate()
        except JoseError as exc:
            # ExpiredTokenError 是 JoseError 子类，单独给出更精确的语义。
            from authlib.jose.errors import ExpiredTokenError as JoseExpiredTokenError

            if isinstance(exc, JoseExpiredTokenError):
                raise ExpiredTokenError(str(exc)) from exc
            raise InvalidTokenError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001 - 非 JOSE 的解析异常同样视为无效令牌
            raise InvalidTokenError(str(exc)) from exc

        token_type = claims.get("typ")
        if token_type != expected_type:
            raise WrongTokenTypeError(f"expected {expected_type} token, got {token_type!r}")
        try:
            user_id = int(claims["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise InvalidTokenError("invalid subject claim") from exc
        return TokenClaims(
            user_id=user_id,
            jti=str(claims.get("jti", "")),
            token_type=expected_type,
            issued_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
            expires_at=datetime.fromtimestamp(int(claims["exp"]), tz=UTC),
        )
