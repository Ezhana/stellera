"""密码哈希：argon2id，经由 pwdlib 的 recommended()（默认 Argon2）。

不自己实现 salt/hash；登录失败时对不存在的用户也执行一次 dummy verify，
降低用户名枚举的时序差异。
"""

from __future__ import annotations

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()

# 模块加载时生成一次，仅用于不存在的用户走一遍同等代价的校验。
_DUMMY_HASH = _hasher.hash("stellera-dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return _hasher.verify(password, hashed_password)
    except Exception:  # noqa: BLE001 - 未知/损坏的 hash 一律视为校验失败
        return False


def dummy_verify() -> None:
    """对固定 dummy hash 执行一次校验，不返回任何判断结果。"""
    verify_password("stellera-dummy-password-for-timing", _DUMMY_HASH)
