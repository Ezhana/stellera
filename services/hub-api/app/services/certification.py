"""认证状态派生：企业 / 工程师认证完全由角色决定，管理员角色不影响认证。"""

from __future__ import annotations

from collections.abc import Iterable

CERTIFICATION_ENTERPRISE = "enterprise"
CERTIFICATION_ENGINEER = "engineer"

# 互斥的两个认证角色：改认证时先全部移除，再加目标角色。
CERTIFICATION_ROLES: tuple[str, ...] = (CERTIFICATION_ENTERPRISE, CERTIFICATION_ENGINEER)


def certification_from_roles(role_names: Iterable[str]) -> str | None:
    """企业优先于工程师；两者都没有则返回 None（未认证）。"""
    roles = set(role_names)
    if CERTIFICATION_ENTERPRISE in roles:
        return CERTIFICATION_ENTERPRISE
    if CERTIFICATION_ENGINEER in roles:
        return CERTIFICATION_ENGINEER
    return None


__all__ = [
    "CERTIFICATION_ENGINEER",
    "CERTIFICATION_ENTERPRISE",
    "CERTIFICATION_ROLES",
    "certification_from_roles",
]
