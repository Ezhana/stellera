"""系统设置业务逻辑：固定 key 的白名单 + 默认值回退。

设置项数量很少，直接整表读取；缺行时回退默认值，管理端列表固定顺序输出。
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_setting import SystemSetting


class SystemSettingInvalidError(Exception):
    """设置项不合法（未知 key / 空值 / 超长），端点映射为 HTTP 422。"""


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    default: str
    max_length: int


# 顺序即管理端与前端展示顺序。
SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition(key="platform_name", default="STELLERA HUB", max_length=64),
    SettingDefinition(
        key="support_contact",
        default="support@stellera.example",
        max_length=128,
    ),
    SettingDefinition(
        key="wallet_recharge_note",
        default="在线充值暂未开放，如需充值请联系平台客服。",
        max_length=300,
    ),
)
SETTINGS_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}


async def get_settings_map(session: AsyncSession) -> dict[str, str]:
    """返回全部设置（含默认值回退）。"""
    stored = {
        row.key: row.value for row in (await session.execute(select(SystemSetting))).scalars()
    }
    return {
        definition.key: stored.get(definition.key, definition.default)
        for definition in SETTING_DEFINITIONS
    }


async def list_settings(session: AsyncSession) -> tuple[SystemSetting, ...]:
    """按固定顺序返回设置行；缺行时返回未落库的默认对象（updated_at 为 None）。"""
    stored = {
        row.key: row
        for row in (
            await session.execute(select(SystemSetting).execution_options(populate_existing=True))
        ).scalars()
    }
    items: list[SystemSetting] = []
    for definition in SETTING_DEFINITIONS:
        row = stored.get(definition.key)
        if row is None:
            # 瞬态对象仅供响应展示（updated_at 未赋值即为 None），不加入 session。
            row = SystemSetting(key=definition.key, value=definition.default)
        items.append(row)
    return tuple(items)


async def update_settings(
    session: AsyncSession,
    values: Mapping[str, str],
    updated_by_id: int,
) -> tuple[SystemSetting, ...]:
    """批量更新设置：先整体校验，再 upsert，最后 commit。"""
    normalized: dict[str, str] = {}
    for key, raw_value in values.items():
        definition = SETTINGS_BY_KEY.get(key)
        if definition is None:
            raise SystemSettingInvalidError(f"未知的设置项：{key}")
        value = raw_value.strip()
        if not value:
            raise SystemSettingInvalidError(f"设置项 {key} 不能为空")
        if len(value) > definition.max_length:
            raise SystemSettingInvalidError(f"设置项 {key} 长度不能超过 {definition.max_length}")
        normalized[key] = value

    existing = {
        row.key: row
        for row in (
            await session.execute(select(SystemSetting).where(SystemSetting.key.in_(normalized)))
        ).scalars()
    }
    for key, value in normalized.items():
        row = existing.get(key)
        if row is None:
            session.add(SystemSetting(key=key, value=value, updated_by_id=updated_by_id))
        else:
            row.value = value
            row.updated_by_id = updated_by_id
    await session.commit()
    return await list_settings(session)


async def ensure_default_settings(session: AsyncSession) -> int:
    """仅插入缺失的设置行（不覆盖已有修改），返回新增数量。"""
    existing = set((await session.execute(select(SystemSetting.key))).scalars())
    created = 0
    for definition in SETTING_DEFINITIONS:
        if definition.key in existing:
            continue
        session.add(SystemSetting(key=definition.key, value=definition.default))
        created += 1
    return created


__all__ = [
    "SETTING_DEFINITIONS",
    "SETTINGS_BY_KEY",
    "SettingDefinition",
    "SystemSettingInvalidError",
    "ensure_default_settings",
    "get_settings_map",
    "list_settings",
    "update_settings",
]
