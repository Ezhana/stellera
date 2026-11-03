"""密码哈希与 JWT 原语的单元测试。"""

from __future__ import annotations

import pytest

from app.core.config import Settings
from app.security.passwords import dummy_verify, hash_password, verify_password
from app.security.tokens import (
    ExpiredTokenError,
    InvalidTokenError,
    TokenService,
    WrongTokenTypeError,
    hash_token,
)


@pytest.fixture()
def token_service() -> TokenService:
    return TokenService(
        Settings(
            app_env="test",
            jwt_secret="unit-test-secret-key-with-at-least-32-chars",
            jwt_issuer="stellera-hub-test",
            jwt_audience="stellera-hub-web-test",
            access_token_ttl_seconds=300,
            refresh_token_ttl_seconds=3600,
        )
    )


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong password", hashed) is False


def test_login_failure_still_runs_dummy_verify() -> None:
    # 不存在的用户走 dummy verify，只要求不抛异常（时序侧信道最小化）。
    dummy_verify()
    assert verify_password("anything", "not-a-valid-hash") is False


def test_access_token_roundtrip(token_service: TokenService) -> None:
    issued = token_service.create_access_token(42)
    claims = token_service.decode_access_token(issued.token)

    assert claims.user_id == 42
    assert claims.jti == issued.jti
    assert claims.token_type == "access"
    assert hash_token(issued.token) != issued.token


def test_refresh_token_cannot_be_used_as_access_token(token_service: TokenService) -> None:
    refresh = token_service.create_refresh_token(42)

    with pytest.raises(WrongTokenTypeError):
        token_service.decode_access_token(refresh.token)


def test_tampered_token_is_rejected(token_service: TokenService) -> None:
    token = token_service.create_access_token(1).token
    tampered = token[:-3] + ("aaa" if token[-3:] != "aaa" else "bbb")

    with pytest.raises(InvalidTokenError):
        token_service.decode_access_token(tampered)


def test_token_signed_by_other_secret_is_rejected(token_service: TokenService) -> None:
    other = TokenService(
        Settings(
            app_env="test",
            jwt_secret="another-unit-test-secret-key-with-32-chars",
            jwt_issuer="stellera-hub-test",
            jwt_audience="stellera-hub-web-test",
        )
    )

    with pytest.raises(InvalidTokenError):
        token_service.decode_access_token(other.create_access_token(1).token)


def test_expired_token_is_rejected() -> None:
    expired_service = TokenService(
        Settings(
            app_env="test",
            jwt_secret="expired-unit-test-secret-key-with-32-chars",
            jwt_issuer="stellera-hub-test",
            jwt_audience="stellera-hub-web-test",
            access_token_ttl_seconds=-60,
        )
    )

    with pytest.raises(ExpiredTokenError):
        expired_service.decode_access_token(expired_service.create_access_token(1).token)


def test_wrong_issuer_is_rejected(token_service: TokenService) -> None:
    # 用同一密钥但不同 iss 的实例签发，claim 校验必须失败。
    other = TokenService(
        Settings(
            app_env="test",
            jwt_secret="unit-test-secret-key-with-at-least-32-chars",
            jwt_issuer="someone-else",
            jwt_audience="stellera-hub-web-test",
        )
    )

    with pytest.raises(InvalidTokenError):
        token_service.decode_access_token(other.create_access_token(1).token)


def test_cors_origins_accept_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """compose/.env 里 CORS_ORIGINS 是逗号分隔字符串，不能被 pydantic-settings 当 JSON 解析。"""
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")

    settings = Settings(_env_file=None)

    assert settings.cors_origins == ["http://a.test", "http://b.test"]
