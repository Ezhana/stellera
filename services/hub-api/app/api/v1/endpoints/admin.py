"""管理后台端点：用户、角色目录、认证审核、兑换码与系统设置。

仅 admin 角色可用：Casbin 的 `/api/v1/*` 通配先拦一次，端点内再按数据库角色
兜底校验（防止策略配置漂移）。认证审核通过后立即刷新 Casbin 投影，无需重新登录。
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, SessionDep, get_enforcer_guard
from app.api.v1.summaries import certification_application_response
from app.middleware.authentication import UserPrincipal
from app.models.base import ensure_utc
from app.models.user import User
from app.rbac.enforcer import EnforcerGuard, load_user_role_names
from app.schemas.admin import (
    AdminRedeemCodeListResponse,
    AdminRedeemCodeResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserUpdateRequest,
    RedeemCodeBatchResponse,
    RedeemCodeCreateRequest,
    RedeemCodeStatus,
    RedeemCodeUpdateRequest,
    RedeemCodeUserRef,
    RoleOptionListResponse,
    RoleOptionResponse,
    SettingItemResponse,
    SettingsListResponse,
    SettingsUpdateRequest,
    WalletAdjustmentRequest,
)
from app.schemas.profile import (
    AdminCertificationApplicationListResponse,
    AdminCertificationApplicationResponse,
    CertificationReviewRequest,
    CertificationStatus,
    CertificationType,
    CertificationUserRef,
)
from app.services import admin as admin_service
from app.services import certification as certification_service
from app.services import system_settings as settings_service
from app.services.admin import (
    AdminRedeemCodeItem,
    AdminUserItem,
    AdminValidationError,
    RoleOption,
)
from app.services.certification import (
    CertificationApplicationItem,
    CertificationError,
    CertificationNotFoundError,
    CertificationValidationError,
    certifications_from_roles,
    display_name,
)
from app.services.system_settings import SystemSetting, SystemSettingInvalidError

router = APIRouter(prefix="/admin", tags=["admin"])


def _http_error(exc: Exception) -> HTTPException:
    """把业务错误映射为 HTTP 状态码：404 / 422 / 409。"""
    if isinstance(exc, (admin_service.AdminNotFoundError, CertificationNotFoundError)):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(
        exc, (AdminValidationError, SystemSettingInvalidError, CertificationValidationError)
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail=str(exc))


async def _require_admin(session: AsyncSession, principal: UserPrincipal) -> None:
    roles = await load_user_role_names(session, principal.user_id)
    if admin_service.ADMIN_ROLE not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _user_response(item: AdminUserItem) -> AdminUserResponse:
    user = item.user
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        nickname=display_name(user),
        full_name=user.full_name,
        email=user.email,
        is_active=user.is_active,
        roles=list(item.roles),
        certifications=list(item.certifications),
        balance_cents=item.balance_cents,
        created_at=ensure_utc(user.created_at),
    )


def _certification_user_ref(item: CertificationApplicationItem) -> CertificationUserRef:
    user = item.user
    return CertificationUserRef(
        id=user.id,
        username=user.username,
        nickname=display_name(user),
        email=user.email,
        roles=list(item.roles),
        certifications=list(certifications_from_roles(item.roles)),
    )


def _admin_certification_application_response(
    item: CertificationApplicationItem,
) -> AdminCertificationApplicationResponse:
    base = certification_application_response(item)
    return AdminCertificationApplicationResponse(
        **base.model_dump(),
        user=_certification_user_ref(item),
    )


def _used_by_ref(user: User | None) -> RedeemCodeUserRef | None:
    if user is None:
        return None
    return RedeemCodeUserRef(id=user.id, display_name=display_name(user))


def _redeem_code_response(item: AdminRedeemCodeItem) -> AdminRedeemCodeResponse:
    code = item.code
    return AdminRedeemCodeResponse(
        id=code.id,
        code=code.code,
        amount_cents=code.amount_cents,
        status=cast(RedeemCodeStatus, code.status),
        batch_no=code.batch_no,
        note=code.note,
        is_expired=item.is_expired,
        used_by=_used_by_ref(item.used_by_user),
        used_at=ensure_utc(code.used_at) if code.used_at is not None else None,
        expires_at=ensure_utc(code.expires_at) if code.expires_at is not None else None,
        created_at=ensure_utc(code.created_at),
    )


def _setting_response(setting: SystemSetting) -> SettingItemResponse:
    updated_at = setting.updated_at
    return SettingItemResponse(
        key=setting.key,
        value=setting.value,
        updated_at=ensure_utc(updated_at) if updated_at is not None else None,
    )


def _settings_response(items: tuple[SystemSetting, ...]) -> SettingsListResponse:
    return SettingsListResponse(items=[_setting_response(item) for item in items])


def _role_option_response(option: RoleOption) -> RoleOptionResponse:
    return RoleOptionResponse(name=option.name, description=option.description)


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    principal: CurrentUserDep,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=120)] = None,
    role: Annotated[str | None, Query(max_length=64)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminUserListResponse:
    """用户列表：支持用户名 / 昵称 / 邮箱 / 实名搜索与角色过滤。"""
    await _require_admin(session, principal)
    page_result = await admin_service.list_users(
        session, q=q, role=role, page=page, page_size=page_size
    )
    return AdminUserListResponse(
        items=[_user_response(item) for item in page_result.items],
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.get("/roles", response_model=RoleOptionListResponse)
async def list_roles(
    principal: CurrentUserDep,
    session: SessionDep,
) -> RoleOptionListResponse:
    """角色目录（不含 authenticated 基线角色）。"""
    await _require_admin(session, principal)
    options = await admin_service.list_roles(session)
    return RoleOptionListResponse(items=[_role_option_response(option) for option in options])


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> AdminUserResponse:
    """更新用户昵称 / 邮箱 / 启用状态；实名与认证只能走认证审核。"""
    await _require_admin(session, principal)
    try:
        item = await admin_service.update_user(
            session,
            actor_id=principal.user_id,
            user_id=user_id,
            nickname=payload.nickname,
            email=payload.email,
            is_active=payload.is_active,
        )
    except admin_service.AdminError as exc:
        raise _http_error(exc) from exc
    return _user_response(item)


@router.post(
    "/users/{user_id}/wallet-adjustments",
    response_model=AdminUserResponse,
)
async def adjust_user_wallet(
    user_id: int,
    payload: WalletAdjustmentRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> AdminUserResponse:
    """管理员余额调整：记一条 adjustment 流水，返回含新余额的用户项。"""
    await _require_admin(session, principal)
    try:
        item = await admin_service.adjust_user_wallet(
            session,
            user_id=user_id,
            direction=payload.direction,
            amount_cents=payload.amount_cents,
            note=payload.note,
        )
    except admin_service.AdminError as exc:
        raise _http_error(exc) from exc
    return _user_response(item)


@router.get(
    "/certification-applications",
    response_model=AdminCertificationApplicationListResponse,
)
async def list_certification_applications(
    principal: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[CertificationStatus | None, Query(alias="status")] = None,
    type_filter: Annotated[CertificationType | None, Query(alias="type")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminCertificationApplicationListResponse:
    """认证申请列表：支持状态 / 类型 / 关键字过滤，最新在前。"""
    await _require_admin(session, principal)
    page_result = await certification_service.list_applications(
        session,
        status=status_filter,
        application_type=type_filter,
        q=q,
        page=page,
        page_size=page_size,
    )
    return AdminCertificationApplicationListResponse(
        items=[_admin_certification_application_response(item) for item in page_result.items],
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.post(
    "/certification-applications/{application_id}/approve",
    response_model=AdminCertificationApplicationResponse,
)
async def approve_certification_application(
    application_id: int,
    principal: CurrentUserDep,
    session: SessionDep,
    guard: Annotated[EnforcerGuard, Depends(get_enforcer_guard)],
    payload: CertificationReviewRequest | None = None,
) -> AdminCertificationApplicationResponse:
    """通过认证申请：写入实名 / 认证角色并立即刷新 Casbin 投影。"""
    await _require_admin(session, principal)
    try:
        item = await certification_service.approve_application(
            session,
            application_id=application_id,
            actor_id=principal.user_id,
            note=payload.note if payload is not None else None,
        )
    except CertificationError as exc:
        raise _http_error(exc) from exc
    guard.resync_user(item.user.id, item.roles)
    return _admin_certification_application_response(item)


@router.post(
    "/certification-applications/{application_id}/reject",
    response_model=AdminCertificationApplicationResponse,
)
async def reject_certification_application(
    application_id: int,
    principal: CurrentUserDep,
    session: SessionDep,
    payload: CertificationReviewRequest | None = None,
) -> AdminCertificationApplicationResponse:
    """驳回认证申请：只改申请状态与审批意见，不动用户角色。"""
    await _require_admin(session, principal)
    try:
        item = await certification_service.reject_application(
            session,
            application_id=application_id,
            actor_id=principal.user_id,
            note=payload.note if payload is not None else None,
        )
    except CertificationError as exc:
        raise _http_error(exc) from exc
    return _admin_certification_application_response(item)


@router.get("/redeem-codes", response_model=AdminRedeemCodeListResponse)
async def list_redeem_codes(
    principal: CurrentUserDep,
    session: SessionDep,
    status_filter: Annotated[RedeemCodeStatus | None, Query(alias="status")] = None,
    q: Annotated[str | None, Query(max_length=120)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> AdminRedeemCodeListResponse:
    """兑换码列表：支持状态与关键字（code / batch_no）过滤。"""
    await _require_admin(session, principal)
    page_result = await admin_service.list_redeem_codes(
        session, status=status_filter, q=q, page=page, page_size=page_size
    )
    return AdminRedeemCodeListResponse(
        items=[_redeem_code_response(item) for item in page_result.items],
        total=page_result.total,
        page=page_result.page,
        page_size=page_result.page_size,
    )


@router.post(
    "/redeem-codes",
    response_model=RedeemCodeBatchResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_redeem_codes(
    payload: RedeemCodeCreateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> RedeemCodeBatchResponse:
    """批量生成兑换码：返回批次号与全部新码。"""
    await _require_admin(session, principal)
    try:
        batch = await admin_service.create_redeem_codes(
            session,
            actor_id=principal.user_id,
            amount_cents=payload.amount_cents,
            quantity=payload.quantity,
            expires_in_days=payload.expires_in_days,
            note=payload.note,
        )
    except admin_service.AdminError as exc:
        raise _http_error(exc) from exc
    return RedeemCodeBatchResponse(
        batch_no=batch.batch_no,
        items=[_redeem_code_response(item) for item in batch.items],
    )


@router.patch("/redeem-codes/{code_id}", response_model=AdminRedeemCodeResponse)
async def update_redeem_code(
    code_id: int,
    payload: RedeemCodeUpdateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> AdminRedeemCodeResponse:
    """启用 / 停用兑换码（已使用的码不允许变更）。"""
    await _require_admin(session, principal)
    try:
        item = await admin_service.update_redeem_code(
            session, code_id=code_id, status=payload.status
        )
    except admin_service.AdminError as exc:
        raise _http_error(exc) from exc
    return _redeem_code_response(item)


@router.get("/settings", response_model=SettingsListResponse)
async def list_settings(
    principal: CurrentUserDep,
    session: SessionDep,
) -> SettingsListResponse:
    """系统设置（固定顺序）：platform_name、support_contact、wallet_recharge_note。"""
    await _require_admin(session, principal)
    return _settings_response(await settings_service.list_settings(session))


@router.patch("/settings", response_model=SettingsListResponse)
async def update_settings(
    payload: SettingsUpdateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> SettingsListResponse:
    """批量更新系统设置；未知 key / 空值 / 超长返回 422。"""
    await _require_admin(session, principal)
    try:
        items = await settings_service.update_settings(session, payload.values, principal.user_id)
    except SystemSettingInvalidError as exc:
        raise _http_error(exc) from exc
    return _settings_response(items)


__all__ = ["router"]
