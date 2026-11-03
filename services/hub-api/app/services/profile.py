"""个人资料与公开主页：资料读写、合作记录与统计。

展示名 / 认证列表统一由 app.services.certification 派生；合作记录只统计已完成订单
（我发布 + 我接单），统计基于全部完成订单，明细按完成时间倒序取最近 20 条。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.fde import FdeOrder
from app.models.user import User
from app.rbac.enforcer import load_user_role_names
from app.services.certification import (
    certifications_from_roles,
    sort_role_names,
)

COMPLETED_ORDER_STATUS = "completed"
ORDER_ROLE_PUBLISHER = "publisher"
ORDER_ROLE_ENGINEER = "engineer"
# 公开主页合作明细分页上限：最近 20 条已完成订单。
COOPERATION_RECORD_LIMIT = 20

NICKNAME_MAX_LENGTH = 64
EMAIL_MAX_LENGTH = 320


class ProfileError(Exception):
    """个人资料业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class ProfileNotFoundError(ProfileError):
    """用户不存在，对应 HTTP 404。"""


class ProfileConflictError(ProfileError):
    """邮箱已被占用等冲突，对应 HTTP 409。"""


class ProfileValidationError(ProfileError):
    """资料字段不合法，对应 HTTP 422。"""


@dataclass(frozen=True)
class CooperationRecord:
    """一条合作记录：订单 + 当前用户角色 + 对方用户（可能为空）。"""

    order: FdeOrder
    role: str
    counterpart: User | None


@dataclass(frozen=True)
class CooperationStats:
    completed_count: int
    partner_count: int
    total_amount_cents: int
    records: tuple[CooperationRecord, ...]


@dataclass(frozen=True)
class Profile:
    user: User
    roles: tuple[str, ...]
    certifications: tuple[str, ...]
    cooperation: CooperationStats


@dataclass(frozen=True)
class PublicProfile:
    user: User
    certifications: tuple[str, ...]
    cooperation: CooperationStats


def _cooperation_role(order: FdeOrder, user_id: int) -> str:
    return ORDER_ROLE_PUBLISHER if order.publisher_id == user_id else ORDER_ROLE_ENGINEER


async def load_cooperation(session: AsyncSession, user_id: int) -> CooperationStats:
    """统计与明细基于同一份「已完成订单」集合，避免口径分叉。"""
    orders = (
        (
            await session.execute(
                select(FdeOrder)
                .where(
                    FdeOrder.status == COMPLETED_ORDER_STATUS,
                    or_(
                        FdeOrder.publisher_id == user_id,
                        FdeOrder.engineer_id == user_id,
                    ),
                )
                .options(
                    selectinload(FdeOrder.publisher),
                    selectinload(FdeOrder.engineer),
                )
                .order_by(
                    FdeOrder.completed_at.is_(None),
                    FdeOrder.completed_at.desc(),
                    FdeOrder.id.desc(),
                )
            )
        )
        .scalars()
        .all()
    )

    partner_ids: set[int] = set()
    records: list[CooperationRecord] = []
    total_amount_cents = 0
    for order in orders:
        total_amount_cents += order.price_cents
        role = _cooperation_role(order, user_id)
        counterpart = order.engineer if role == ORDER_ROLE_PUBLISHER else order.publisher
        if counterpart is not None:
            partner_ids.add(counterpart.id)
        if len(records) < COOPERATION_RECORD_LIMIT:
            records.append(CooperationRecord(order=order, role=role, counterpart=counterpart))

    return CooperationStats(
        completed_count=len(orders),
        partner_count=len(partner_ids),
        total_amount_cents=total_amount_cents,
        records=tuple(records),
    )


async def _build_profile(session: AsyncSession, user: User) -> Profile:
    roles = sort_role_names(await load_user_role_names(session, user.id))
    return Profile(
        user=user,
        roles=roles,
        certifications=certifications_from_roles(roles),
        cooperation=await load_cooperation(session, user.id),
    )


async def _require_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise ProfileNotFoundError("用户不存在")
    return user


async def get_profile(session: AsyncSession, user_id: int) -> Profile:
    """本人资料：含邮箱、实名与联系方式，以及合作记录。"""
    return await _build_profile(session, await _require_user(session, user_id))


async def get_public_profile(session: AsyncSession, user_id: int) -> PublicProfile:
    """公开主页：隐藏实名 / 邮箱 / 联系方式与角色，只保留展示所需信息。"""
    user = await _require_user(session, user_id)
    roles = sort_role_names(await load_user_role_names(session, user.id))
    return PublicProfile(
        user=user,
        certifications=certifications_from_roles(roles),
        cooperation=await load_cooperation(session, user.id),
    )


def _normalize_optional(value: str | None) -> str | None:
    """空字符串表示清空；None 表示不修改（由调用方区分传入与否）。"""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


async def update_profile(
    session: AsyncSession,
    *,
    user_id: int,
    nickname: str | None = None,
    email: str | None = None,
    bio: str | None = None,
    skills: str | None = None,
    city: str | None = None,
    contact_phone: str | None = None,
    contact_wechat: str | None = None,
) -> Profile:
    """更新个人资料：nickname / email 不可清空，其余字段空字符串表示清空。"""
    user = await _require_user(session, user_id)
    if all(
        value is None
        for value in (nickname, email, bio, skills, city, contact_phone, contact_wechat)
    ):
        raise ProfileValidationError("至少需要修改一项")

    if nickname is not None:
        normalized_nickname = nickname.strip()
        if not 1 <= len(normalized_nickname) <= NICKNAME_MAX_LENGTH:
            raise ProfileValidationError("昵称长度需在 1-64 个字符之间")
        user.nickname = normalized_nickname

    if email is not None:
        normalized_email = email.strip().lower()
        if not 3 <= len(normalized_email) <= EMAIL_MAX_LENGTH or "@" not in normalized_email:
            raise ProfileValidationError("邮箱格式不正确")
        conflict = (
            await session.execute(
                select(User.id)
                .where(
                    func.lower(User.email) == normalized_email,
                    User.id != user_id,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if conflict is not None:
            raise ProfileConflictError("邮箱已被注册")
        user.email = normalized_email

    user.bio = _normalize_optional(bio) if bio is not None else user.bio
    user.skills = _normalize_optional(skills) if skills is not None else user.skills
    user.city = _normalize_optional(city) if city is not None else user.city
    user.contact_phone = (
        _normalize_optional(contact_phone) if contact_phone is not None else user.contact_phone
    )
    user.contact_wechat = (
        _normalize_optional(contact_wechat) if contact_wechat is not None else user.contact_wechat
    )

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ProfileConflictError("邮箱已被注册") from exc
    return await _build_profile(session, user)


__all__ = [
    "COOPERATION_RECORD_LIMIT",
    "CooperationRecord",
    "CooperationStats",
    "Profile",
    "ProfileConflictError",
    "ProfileError",
    "ProfileNotFoundError",
    "ProfileValidationError",
    "PublicProfile",
    "get_profile",
    "get_public_profile",
    "load_cooperation",
    "update_profile",
]
