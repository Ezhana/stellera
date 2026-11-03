"""身份派生与认证申请审核：展示名、认证列表与三类认证的申请 / 审批。

认证列表完全由角色派生（realname / enterprise / engineer），admin 不影响认证；
展示名统一为 `nickname → full_name → username`。审核通过后同步 users.full_name
与 user_roles，并把审批结果写回申请行。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.base import utcnow
from app.models.certification import CertificationApplication
from app.models.rbac import Role, UserRole
from app.models.user import User
from app.rbac.enforcer import load_user_role_names

ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"

CERTIFICATION_REALNAME = "realname"
CERTIFICATION_ENTERPRISE = "enterprise"
CERTIFICATION_ENGINEER = "engineer"

# 认证展示顺序固定：实名、企业、工程师。realname 只是认证身份，不授予业务权限。
CERTIFICATION_DISPLAY_ORDER: tuple[str, ...] = (
    CERTIFICATION_REALNAME,
    CERTIFICATION_ENTERPRISE,
    CERTIFICATION_ENGINEER,
)
# 企业 / 工程师互斥：新通过时先移除两者，再加入目标角色。
BUSINESS_CERTIFICATION_ROLES: tuple[str, ...] = (
    CERTIFICATION_ENTERPRISE,
    CERTIFICATION_ENGINEER,
)
CERTIFICATION_ROLES: tuple[str, ...] = (
    CERTIFICATION_REALNAME,
    *BUSINESS_CERTIFICATION_ROLES,
)

# 角色展示顺序（管理端角色目录与用户角色列表共用）。
ROLE_DISPLAY_ORDER: tuple[str, ...] = (ADMIN_ROLE, MEMBER_ROLE, *CERTIFICATION_DISPLAY_ORDER)

APPLICATION_STATUS_PENDING = "pending"
APPLICATION_STATUS_APPROVED = "approved"
APPLICATION_STATUS_REJECTED = "rejected"

# 各类型必填字段（长度上限由 schema 校验，这里只保证非空）。
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    CERTIFICATION_REALNAME: ("real_name", "id_number", "contact_phone"),
    CERTIFICATION_ENTERPRISE: ("company_name", "credit_code", "contact_name", "contact_phone"),
    CERTIFICATION_ENGINEER: ("skills", "work_years", "project_experience", "contact_phone"),
}

REVIEW_NOTE_REPLACED = "已通过其他认证"


class CertificationError(Exception):
    """认证业务错误基类；端点按具体子类映射 HTTP 状态码。"""


class CertificationNotFoundError(CertificationError):
    """申请不存在，对应 HTTP 404。"""


class CertificationConflictError(CertificationError):
    """状态冲突（重复申请、已处理、未实名等），对应 HTTP 409。"""


class CertificationValidationError(CertificationError):
    """申请字段不合法，对应 HTTP 422。"""


@dataclass(frozen=True)
class CertificationApplicationItem:
    """申请项 + 申请人 + 申请人当前角色（审批后用于刷新 Casbin 投影）。"""

    application: CertificationApplication
    user: User
    roles: tuple[str, ...]


@dataclass(frozen=True)
class CertificationApplicationPage:
    items: tuple[CertificationApplicationItem, ...]
    total: int
    page: int
    page_size: int


def certifications_from_roles(role_names: Iterable[str]) -> tuple[str, ...]:
    """从角色名派生认证列表，顺序固定为 realname、enterprise、engineer。"""
    roles = set(role_names)
    return tuple(name for name in CERTIFICATION_DISPLAY_ORDER if name in roles)


def display_name(user: User) -> str:
    """统一展示名：昵称优先，其次实名，最后用户名。"""
    return user.nickname or user.full_name or user.username


def sort_role_names(names: Iterable[str]) -> tuple[str, ...]:
    """按固定展示顺序排序角色名（未知角色排在最后并按字母序）。"""
    unique = set(names)
    return tuple(
        sorted(
            unique,
            key=lambda name: (
                ROLE_DISPLAY_ORDER.index(name)
                if name in ROLE_DISPLAY_ORDER
                else len(ROLE_DISPLAY_ORDER),
                name,
            ),
        )
    )


async def roles_by_user(session: AsyncSession, user_ids: list[int]) -> dict[int, tuple[str, ...]]:
    """批量读取用户角色，避免列表页逐条查询。"""
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


def _application_options() -> list[Any]:
    return [
        selectinload(CertificationApplication.user),
        selectinload(CertificationApplication.reviewer),
    ]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _clean_fields(fields: dict[str, str | int | None]) -> dict[str, str | int | None]:
    return {
        key: (value.strip() if isinstance(value, str) else value)
        for key, value in fields.items()
        if value is not None and not (isinstance(value, str) and not value.strip())
    }


async def _require_user(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise CertificationNotFoundError("用户不存在")
    return user


async def _has_realname(session: AsyncSession, user: User, role_names: Iterable[str]) -> bool:
    if CERTIFICATION_REALNAME in set(role_names):
        return True
    approved = (
        await session.execute(
            select(CertificationApplication.id)
            .where(
                CertificationApplication.user_id == user.id,
                CertificationApplication.type == CERTIFICATION_REALNAME,
                CertificationApplication.status == APPLICATION_STATUS_APPROVED,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return approved is not None


async def _existing_status(
    session: AsyncSession, *, user_id: int, application_type: str
) -> str | None:
    """同类型最近一条申请的状态（pending 优先于 approved 判断）。"""
    statuses = (
        (
            await session.execute(
                select(CertificationApplication.status).where(
                    CertificationApplication.user_id == user_id,
                    CertificationApplication.type == application_type,
                )
            )
        )
        .scalars()
        .all()
    )
    if APPLICATION_STATUS_PENDING in statuses:
        return APPLICATION_STATUS_PENDING
    if APPLICATION_STATUS_APPROVED in statuses:
        return APPLICATION_STATUS_APPROVED
    return None


async def _sync_roles(
    session: AsyncSession, *, user_id: int, role_names: Iterable[str]
) -> tuple[str, ...]:
    """把 user_roles 收敛到目标角色集合（只增删差异行）。"""
    target = set(role_names)
    roles = {
        role.name: role
        for role in (await session.execute(select(Role).where(Role.name.in_(target)))).scalars()
    }
    missing = target - set(roles)
    if missing:
        raise CertificationValidationError("角色数据未初始化，请联系管理员")
    target_ids = {roles[name].id for name in target}
    existing_ids = set(
        (await session.execute(select(UserRole.role_id).where(UserRole.user_id == user_id)))
        .scalars()
        .all()
    )
    stale_ids = existing_ids - target_ids
    if stale_ids:
        await session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id.in_(stale_ids),
            )
        )
    for role_id in target_ids - existing_ids:
        session.add(UserRole(user_id=user_id, role_id=role_id))
    await session.flush()
    return sort_role_names(target)


async def list_my_applications(
    session: AsyncSession, *, user_id: int, limit: int = 50
) -> tuple[CertificationApplicationItem, ...]:
    """当前用户的全部认证申请，最新在前。"""
    user = await _require_user(session, user_id)
    rows = (
        (
            await session.execute(
                select(CertificationApplication)
                .where(CertificationApplication.user_id == user_id)
                .options(*_application_options())
                .order_by(
                    CertificationApplication.created_at.desc(), CertificationApplication.id.desc()
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    roles = sort_role_names(await load_user_role_names(session, user_id))
    return tuple(
        CertificationApplicationItem(application=row, user=user, roles=roles) for row in rows
    )


async def create_application(
    session: AsyncSession,
    *,
    user_id: int,
    application_type: str,
    fields: dict[str, str | int | None],
) -> CertificationApplicationItem:
    """提交认证申请：类型校验 + 重复校验 + 企业/工程师需先完成实名。"""
    if application_type not in CERTIFICATION_ROLES:
        raise CertificationValidationError("认证类型不合法")
    user = await _require_user(session, user_id)
    role_names = await load_user_role_names(session, user_id)
    cleaned = _clean_fields(fields)

    if application_type == CERTIFICATION_REALNAME:
        if await _has_realname(session, user, role_names):
            raise CertificationConflictError("该类型认证已通过")
    else:
        if not await _has_realname(session, user, role_names):
            raise CertificationConflictError("请先完成实名认证")

    status = await _existing_status(session, user_id=user_id, application_type=application_type)
    if status == APPLICATION_STATUS_PENDING:
        raise CertificationConflictError("该类型认证正在审核中")
    if status == APPLICATION_STATUS_APPROVED:
        raise CertificationConflictError("该类型认证已通过")

    missing = [name for name in REQUIRED_FIELDS[application_type] if cleaned.get(name) is None]
    if missing:
        raise CertificationValidationError("请填写完整的认证信息")
    work_years = cleaned.get("work_years")
    if application_type == CERTIFICATION_ENGINEER and (
        not isinstance(work_years, int) or not 0 <= work_years <= 60
    ):
        raise CertificationValidationError("工作年限需在 0-60 之间")

    application = CertificationApplication(
        user_id=user_id,
        type=application_type,
        status=APPLICATION_STATUS_PENDING,
        created_at=utcnow(),
        **cleaned,
    )
    session.add(application)
    await session.flush()
    await session.commit()
    return CertificationApplicationItem(
        application=application,
        user=user,
        roles=sort_role_names(role_names),
    )


async def _get_application(session: AsyncSession, application_id: int) -> CertificationApplication:
    application = (
        await session.execute(
            select(CertificationApplication)
            .where(CertificationApplication.id == application_id)
            .options(*_application_options())
        )
    ).scalar_one_or_none()
    if application is None:
        raise CertificationNotFoundError("认证申请不存在")
    return application


async def _item_for(
    session: AsyncSession, application: CertificationApplication
) -> CertificationApplicationItem:
    roles = await load_user_role_names(session, application.user_id)
    return CertificationApplicationItem(
        application=application,
        user=application.user,
        roles=sort_role_names(roles),
    )


async def _reject_pending_business_applications(
    session: AsyncSession,
    *,
    user_id: int,
    exclude_id: int,
    reviewer_id: int,
    reviewed_at: datetime,
) -> None:
    """同一用户其它 pending 的企业 / 工程师申请自动驳回（认证互斥）。"""
    await session.execute(
        update(CertificationApplication)
        .where(
            CertificationApplication.user_id == user_id,
            CertificationApplication.type.in_(BUSINESS_CERTIFICATION_ROLES),
            CertificationApplication.status == APPLICATION_STATUS_PENDING,
            CertificationApplication.id != exclude_id,
        )
        .values(
            status=APPLICATION_STATUS_REJECTED,
            review_note=REVIEW_NOTE_REPLACED,
            reviewer_id=reviewer_id,
            reviewed_at=reviewed_at,
        )
        .execution_options(synchronize_session=False)
    )


async def approve_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int,
    note: str | None = None,
) -> CertificationApplicationItem:
    """管理员通过认证申请：同步实名 / 认证角色并返回最新申请项。"""
    application = await _get_application(session, application_id)
    if application.status != APPLICATION_STATUS_PENDING:
        raise CertificationConflictError("申请已处理，无法重复审批")
    reviewer = await _require_user(session, actor_id)
    user = application.user
    current_roles = set(await load_user_role_names(session, user.id))

    if application.type == CERTIFICATION_REALNAME:
        real_name = _clean(application.real_name)
        if real_name is None:
            raise CertificationValidationError("实名申请缺少姓名")
        user.full_name = real_name
        current_roles.add(CERTIFICATION_REALNAME)
    elif application.type in BUSINESS_CERTIFICATION_ROLES:
        if not await _has_realname(session, user, current_roles):
            raise CertificationConflictError("请先完成实名认证")
        current_roles -= set(BUSINESS_CERTIFICATION_ROLES)
        current_roles.add(application.type)
    else:
        raise CertificationValidationError("认证类型不合法")
    current_roles.add(MEMBER_ROLE)

    roles = await _sync_roles(session, user_id=user.id, role_names=current_roles)

    now = utcnow()
    if application.type in BUSINESS_CERTIFICATION_ROLES:
        await _reject_pending_business_applications(
            session,
            user_id=user.id,
            exclude_id=application.id,
            reviewer_id=reviewer.id,
            reviewed_at=now,
        )

    application.status = APPLICATION_STATUS_APPROVED
    application.review_note = _clean(note)
    application.reviewer = reviewer
    application.reviewed_at = now
    await session.flush()
    await session.commit()
    return CertificationApplicationItem(application=application, user=user, roles=roles)


async def reject_application(
    session: AsyncSession,
    *,
    application_id: int,
    actor_id: int,
    note: str | None = None,
) -> CertificationApplicationItem:
    """管理员驳回认证申请：只改申请状态，不动用户角色。"""
    application = await _get_application(session, application_id)
    if application.status != APPLICATION_STATUS_PENDING:
        raise CertificationConflictError("申请已处理，无法重复审批")
    reviewer = await _require_user(session, actor_id)
    application.status = APPLICATION_STATUS_REJECTED
    application.review_note = _clean(note)
    application.reviewer = reviewer
    application.reviewed_at = utcnow()
    await session.flush()
    await session.commit()
    return await _item_for(session, application)


async def list_applications(
    session: AsyncSession,
    *,
    status: str | None = None,
    application_type: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> CertificationApplicationPage:
    """管理端认证申请列表：状态 / 类型 / 关键字过滤，最新在前。"""
    filters: list[Any] = []
    if status is not None:
        filters.append(CertificationApplication.status == status)
    if application_type is not None:
        filters.append(CertificationApplication.type == application_type)
    if q is not None and q.strip():
        pattern = f"%{q.strip()}%"
        matching_users = select(User.id).where(
            or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
        filters.append(
            or_(
                CertificationApplication.company_name.ilike(pattern),
                CertificationApplication.user_id.in_(matching_users),
            )
        )

    rows = (
        (
            await session.execute(
                select(CertificationApplication)
                .where(*filters)
                .options(*_application_options())
                .order_by(
                    CertificationApplication.created_at.desc(),
                    CertificationApplication.id.desc(),
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .scalars()
        .all()
    )
    total = (
        await session.execute(
            select(func.count()).select_from(CertificationApplication).where(*filters)
        )
    ).scalar_one()
    roles = await roles_by_user(session, [row.user_id for row in rows])
    items = tuple(
        CertificationApplicationItem(
            application=row,
            user=row.user,
            roles=roles.get(row.user_id, ()),
        )
        for row in rows
    )
    return CertificationApplicationPage(items=items, total=total, page=page, page_size=page_size)


__all__ = [
    "ADMIN_ROLE",
    "APPLICATION_STATUS_APPROVED",
    "APPLICATION_STATUS_PENDING",
    "APPLICATION_STATUS_REJECTED",
    "BUSINESS_CERTIFICATION_ROLES",
    "CERTIFICATION_DISPLAY_ORDER",
    "CERTIFICATION_ENGINEER",
    "CERTIFICATION_REALNAME",
    "CERTIFICATION_ROLES",
    "CERTIFICATION_ENTERPRISE",
    "CertificationApplicationItem",
    "CertificationApplicationPage",
    "CertificationConflictError",
    "CertificationError",
    "CertificationNotFoundError",
    "CertificationValidationError",
    "MEMBER_ROLE",
    "REVIEW_NOTE_REPLACED",
    "ROLE_DISPLAY_ORDER",
    "approve_application",
    "certifications_from_roles",
    "create_application",
    "display_name",
    "list_applications",
    "list_my_applications",
    "reject_application",
    "roles_by_user",
    "sort_role_names",
]
