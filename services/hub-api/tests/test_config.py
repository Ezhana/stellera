"""Settings 的逗号分隔字段解析。

全部用 ``Settings(_env_file=None, ...)`` 构造，避免测试受服务目录下 .env 影响。
"""

from __future__ import annotations

from app.core.config import Settings


def test_debug_flags_parse_from_csv() -> None:
    settings = Settings(_env_file=None, debug="db_echo, sql")

    assert settings.debug == ["db_echo", "sql"]


def test_empty_debug_is_empty_list() -> None:
    settings = Settings(_env_file=None, debug="")

    assert settings.debug == []


def test_cors_origins_parse_from_csv() -> None:
    settings = Settings(_env_file=None, cors_origins="http://a, http://b")

    assert settings.cors_origins == ["http://a", "http://b"]
