"""管理后台业务逻辑：用户编辑与余额调整、兑换码、角色目录。

所有写操作都集中在这里做校验与保护，端点只负责 HTTP 语义。
用户资料只允许改昵称 / 邮箱 / 启用状态；实名与认证只能通过认证审核流程变更，
管理端不再直接修改 full_name 或认证角色。
"""

from __future__ import annotations

import re
import secrets
import string
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import ensure_utc, utcnow
from app.models.rbac import Role, UserRole
from app.models.redeem import RedeemCode
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.models.wallet import Wallet
from app.rbac.enforcer import AUTHENTICATED_ROLE, load_user_role_names
from app.services import wallet as wallet_service
from app.services.certification import (
    ADMIN_ROLE,
    ROLE_DISPLAY_ORDER,
    certifications_from_roles,
    sort_role_names,
)
from app.services.wallet import REDEEM_STATUS_ACTIVE, REDEEM_STATUS_USED

# 兑换码去掉易混字符 I/O/0/1，避免人工输入时看错。
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
BATCH_ALPHABET = string.ascii_uppercase + string.digits

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AdminError(Exception):
    """管理后台业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class AdminNotFoundError(AdminError):
    """资源不存在，对应 HTTP 404。"""


class AdminConflictError(AdminError):
    """与保护规则冲突（停用自己、移除最后管理员、邮箱占用等），对应 HTTP 409。"""


class AdminValidationError(AdminError):
    """参数不合法（昵称 / 邮箱格式等），对应 HTTP 422。"""


@dataclass(frozen=True)
class AdminUserItem:
    """管理端用户列表项：用户 + 角色列表 + 认证列表 + 钱包余额。"""

    user: User
    roles: tuple[str, ...]
    certifications: tuple[str, ...]
    balance_cents: int


@dataclass(frozen=True)
class AdminUserPage:
    items: tuple[AdminUserItem, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class RoleOption:
    name: str
    description: str | None


@dataclass(frozen=True)
class AdminRedeemCodeItem:
    code: RedeemCode
    used_by_user: User | None
    is_expired: bool


@dataclass(frozen=True)
class AdminRedeemCodePage:
    items: tuple[AdminRedeemCodeItem, ...]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class RedeemCodeBatch:
    """一次批量生成的兑换码。"""

    batch_no: str
    items: tuple[AdminRedeemCodeItem, ...]


async def _roles_by_user(session: AsyncSession, user_ids: list[int]) -> dict[int, tuple[str, ...]]:
    if not user_ids:
        return {}
    rows = (
        await session.execute(
            select(UserRole.user_id, Role.name)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id.in_(user_ids))
        )
    ).all()
    grouped: dict[int, list[str]] = {}
    for user_id, role_name in rows:
        grouped.setdefault(user_id, []).append(role_name)
    return {user_id: sort_role_names(names) for user_id, names in grouped.items()}


async def _wallet_balance(session: AsyncSession, user_id: int) -> int:
    balance = (
        await session.execute(select(Wallet.balance_cents).where(Wallet.user_id == user_id))
    ).scalar_one_or_none()
    return int(balance or 0)


def _user_item_from(user: User, roles: tuple[str, ...], balance_cents: int) -> AdminUserItem:
    return AdminUserItem(
        user=user,
        roles=roles,
        certifications=certifications_from_roles(roles),
        balance_cents=balance_cents,
    )


async def _user_item(session: AsyncSession, user: User) -> AdminUserItem:
    return _user_item_from(
        user,
        sort_role_names(await load_user_role_names(session, user.id)),
        await _wallet_balance(session, user.id),
    )


async def list_users(
    session: AsyncSession,
    *,
    q: str | None = None,
    role: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AdminUserPage:
    """用户列表：无钱包按 0 计余额；按 users.id 升序保证分页稳定。"""
    filters = []
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(
            or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            )
        )
    if role is not None:
        filters.append(
            User.id.in_(
                select(UserRole.user_id)
                .join(Role, Role.id == UserRole.role_id)
                .where(Role.name == role)
            )
        )

    rows = (
        await session.execute(
            select(User, func.coalesce(Wallet.balance_cents, 0))
            .outerjoin(Wallet, Wallet.user_id == User.id)
            .where(*filters)
            .order_by(User.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    total = (
        await session.execute(select(func.count()).select_from(User).where(*filters))
    ).scalar_one()

    roles_by_user = await _roles_by_user(session, [row[0].id for row in rows])
    items = tuple(
        _user_item_from(row[0], roles_by_user.get(row[0].id, ()), int(row[1])) for row in rows
    )
    return AdminUserPage(items=items, total=total, page=page, page_size=page_size)


async def list_roles(session: AsyncSession) -> tuple[RoleOption, ...]:
    """角色目录：排除 authenticated，按固定顺序输出。"""
    rows = (await session.execute(select(Role))).scalars().all()
    by_name = {role.name: role for role in rows}
    ordered = [name for name in ROLE_DISPLAY_ORDER if name in by_name]
    ordered.extend(
        sorted(
            name
            for name in by_name
            if name not in ROLE_DISPLAY_ORDER and name != AUTHENTICATED_ROLE
        )
    )
    return tuple(RoleOption(name=name, description=by_name[name].description) for name in ordered)


async def _admin_count(session: AsyncSession) -> int:
    return (
        await session.execute(
            select(func.count(func.distinct(UserRole.user_id)))
            .select_from(UserRole)
            .join(Role, Role.id == UserRole.role_id)
            .where(Role.name == ADMIN_ROLE)
        )
    ).scalar_one()


async def update_user(
    session: AsyncSession,
    *,
    actor_id: int,
    user_id: int,
    nickname: str | None = None,
    email: str | None = None,
    is_active: bool | None = None,
) -> AdminUserItem:
    """更新昵称 / 邮箱 / 启用状态，并施加管理员保护规则。

    full_name（实名）与认证角色不在这里改：只能由认证审核通过后写入。
    """
    user = await session.get(User, user_id)
    if user is None:
        raise AdminNotFoundError("用户不存在")
    if nickname is None and email is None and is_active is None:
        raise AdminValidationError("至少需要修改一项")

    current_roles = set(await load_user_role_names(session, user_id))

    if nickname is not None:
        normalized_nickname = nickname.strip()
        if not 1 <= len(normalized_nickname) <= 64:
            raise AdminValidationError("昵称长度需在 1-64 个字符之间")
        user.nickname = normalized_nickname

    if email is not None:
        normalized_email = email.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalized_email):
            raise AdminValidationError("邮箱格式不正确")
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
            raise AdminConflictError("邮箱已被注册")
        user.email = normalized_email

    if actor_id == user_id and is_active is False:
        raise AdminConflictError("不能停用当前登录账号")
    loses_admin = ADMIN_ROLE in current_roles and is_active is False
    if loses_admin and await _admin_count(session) <= 1:
        raise AdminConflictError("不能移除最后一个管理员")
    if is_active is not None:
        user.is_active = is_active
        if not is_active:
            # 停用后立即吊销全部未吊销的 refresh token。
            await session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=utcnow())
            )

    await session.commit()
    return await _user_item(session, user)


async def adjust_user_wallet(
    session: AsyncSession,
    *,
    user_id: int,
    direction: str,
    amount_cents: int,
    note: str,
) -> AdminUserItem:
    """管理员余额调整：写一条 adjustment 流水，余额只随流水变化。"""
    user = await session.get(User, user_id)
    if user is None:
        raise AdminNotFoundError("用户不存在")
    wallet = await wallet_service.get_or_create_wallet(session, user_id, for_update=True)
    description = f"管理员调整：{note.strip()}"
    if direction == wallet_service.DIRECTION_CREDIT:
        await wallet_service.credit(
            session,
            wallet,
            amount_cents,
            type=wallet_service.TRANSACTION_TYPE_ADJUSTMENT,
            description=description,
        )
    elif direction == wallet_service.DIRECTION_DEBIT:
        try:
            await wallet_service.debit(
                session,
                wallet,
                amount_cents,
                type=wallet_service.TRANSACTION_TYPE_ADJUSTMENT,
                description=description,
            )
        except wallet_service.WalletConflictError as exc:
            raise AdminConflictError("余额不足，无法扣减") from exc
    else:
        raise AdminValidationError("调整方向不合法")
    await session.commit()
    return await _user_item(session, user)


def _new_code() -> str:
    groups = ["".join(secrets.choice(CODE_ALPHABET) for _ in range(4)) for _ in range(3)]
    return f"RDM-{groups[0]}-{groups[1]}-{groups[2]}"


async def create_redeem_codes(
    session: AsyncSession,
    *,
    actor_id: int,
    amount_cents: int,
    quantity: int,
    expires_in_days: int | None,
    note: str | None,
) -> RedeemCodeBatch:
    """批量生成兑换码：批内与库内唯一，冲突自动重生成。"""
    now = utcnow()
    batch_no = f"RDM-{now:%Y%m%d}-{''.join(secrets.choice(BATCH_ALPHABET) for _ in range(4))}"
    codes: list[str] = []
    seen: set[str] = set()
    while True:
        while len(codes) < quantity:
            candidate = _new_code()
            if candidate in seen:
                continue
            seen.add(candidate)
            codes.append(candidate)
        existing = set(
            (
                await session.execute(select(RedeemCode.code).where(RedeemCode.code.in_(codes)))
            ).scalars()
        )
        if not existing:
            break
        codes = [code for code in codes if code not in existing]

    expires_at = now + timedelta(days=expires_in_days) if expires_in_days is not None else None
    records = [
        RedeemCode(
            code=code,
            amount_cents=amount_cents,
            status=REDEEM_STATUS_ACTIVE,
            batch_no=batch_no,
            note=note,
            created_by_id=actor_id,
            expires_at=expires_at,
            created_at=now,
        )
        for code in codes
    ]
    session.add_all(records)
    await session.commit()
    return RedeemCodeBatch(
        batch_no=batch_no,
        items=tuple(_redeem_item(record, now=now) for record in records),
    )


def _redeem_item(code: RedeemCode, *, now: datetime | None = None) -> AdminRedeemCodeItem:
    current = now or utcnow()
    is_expired = code.expires_at is not None and ensure_utc(code.expires_at) <= current
    return AdminRedeemCodeItem(code=code, used_by_user=code.used_by, is_expired=is_expired)


async def list_redeem_codes(
    session: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AdminRedeemCodePage:
    """兑换码列表：最新在前，按状态 / 关键字（code、batch_no）过滤。"""
    filters = []
    if status is not None:
        filters.append(RedeemCode.status == status)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        filters.append(or_(RedeemCode.code.ilike(pattern), RedeemCode.batch_no.ilike(pattern)))

    rows = (
        (
            await session.execute(
                select(RedeemCode)
                .where(*filters)
                .options(selectinload(RedeemCode.used_by))
                .order_by(RedeemCode.created_at.desc(), RedeemCode.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    total = (
        await session.execute(select(func.count()).select_from(RedeemCode).where(*filters))
    ).scalar_one()
    now = utcnow()
    return AdminRedeemCodePage(
        items=tuple(_redeem_item(row, now=now) for row in rows),
        total=total,
        page=page,
        page_size=page_size,
    )


async def update_redeem_code(
    session: AsyncSession, *, code_id: int, status: str
) -> AdminRedeemCodeItem:
    """启用 / 停用兑换码；已使用与已过期（仅启用方向）的码不允许变更。"""
    code = (
        await session.execute(
            select(RedeemCode)
            .options(selectinload(RedeemCode.used_by))
            .where(RedeemCode.id == code_id)
        )
    ).scalar_one_or_none()
    if code is None:
        raise AdminNotFoundError("兑换码不存在")
    if code.status == REDEEM_STATUS_USED:
        raise AdminConflictError("已使用的兑换码不能修改状态")
    if code.status == status:
        return _redeem_item(code)

    now = utcnow()
    if (
        status == REDEEM_STATUS_ACTIVE
        and code.expires_at is not None
        and ensure_utc(code.expires_at) <= now
    ):
        raise AdminConflictError("已过期的兑换码不能启用")
    code.status = status
    await session.commit()
    return _redeem_item(code, now=now)


__all__ = [
    "AdminConflictError",
    "AdminError",
    "AdminNotFoundError",
    "AdminRedeemCodeItem",
    "AdminRedeemCodePage",
    "AdminUserItem",
    "AdminUserPage",
    "AdminValidationError",
    "RedeemCodeBatch",
    "RoleOption",
    "adjust_user_wallet",
    "create_redeem_codes",
    "list_redeem_codes",
    "list_roles",
    "list_users",
    "update_redeem_code",
    "update_user",
]
