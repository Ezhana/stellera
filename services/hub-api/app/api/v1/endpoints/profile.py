"""个人信息、公开主页与认证申请端点。

认证用户可读写自己的资料、提交认证申请；登录用户都可以查看他人公开主页
（隐藏实名 / 邮箱 / 联系方式 / 角色）。认证审核在管理后台完成。
"""

from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.summaries import certification_application_response
from app.models.base import ensure_utc
from app.models.user import User
from app.schemas.profile import (
    CertificationApplicationCreateRequest,
    CertificationApplicationListResponse,
    CertificationApplicationResponse,
    CooperationCounterpart,
    CooperationRecordResponse,
    CooperationResponse,
    CooperationRole,
    ProfileResponse,
    ProfileUpdateRequest,
    PublicProfileResponse,
)
from app.services import certification as certification_service
from app.services import profile as profile_service
from app.services.certification import (
    CertificationError,
    CertificationNotFoundError,
    CertificationValidationError,
    certifications_from_roles,
    display_name,
)
from app.services.profile import (
    CooperationStats,
    Profile,
    ProfileError,
    ProfileNotFoundError,
    ProfileValidationError,
    PublicProfile,
)

router = APIRouter(tags=["profile"])


def _counterpart_ref(user: User | None) -> CooperationCounterpart | None:
    if user is None:
        return None
    return CooperationCounterpart(
        id=user.id,
        display_name=display_name(user),
        certifications=list(certifications_from_roles(role.name for role in user.roles)),
    )


def _cooperation_response(stats: CooperationStats) -> CooperationResponse:
    return CooperationResponse(
        completed_count=stats.completed_count,
        partner_count=stats.partner_count,
        total_amount_cents=stats.total_amount_cents,
        records=[
            CooperationRecordResponse(
                order_id=record.order.id,
                code=record.order.code,
                title=record.order.title,
                price_cents=record.order.price_cents,
                completed_at=(
                    ensure_utc(record.order.completed_at)
                    if record.order.completed_at is not None
                    else None
                ),
                role=cast(CooperationRole, record.role),
                counterpart=_counterpart_ref(record.counterpart),
            )
            for record in stats.records
        ],
    )


def _profile_response(profile: Profile) -> ProfileResponse:
    user = profile.user
    return ProfileResponse(
        id=user.id,
        username=user.username,
        nickname=display_name(user),
        email=user.email,
        real_name=user.full_name,
        bio=user.bio,
        skills=user.skills,
        city=user.city,
        contact_phone=user.contact_phone,
        contact_wechat=user.contact_wechat,
        roles=list(profile.roles),
        certifications=list(profile.certifications),
        created_at=ensure_utc(user.created_at),
        cooperation=_cooperation_response(profile.cooperation),
    )


def _public_profile_response(profile: PublicProfile) -> PublicProfileResponse:
    user = profile.user
    return PublicProfileResponse(
        id=user.id,
        nickname=display_name(user),
        bio=user.bio,
        skills=user.skills,
        city=user.city,
        certifications=list(profile.certifications),
        member_since=ensure_utc(user.created_at),
        cooperation=_cooperation_response(profile.cooperation),
    )


def _http_error(exc: Exception) -> HTTPException:
    """把业务错误映射为 HTTP 状态码：404 / 422 / 409。"""
    if isinstance(exc, (ProfileNotFoundError, CertificationNotFoundError)):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (ProfileValidationError, CertificationValidationError)):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        status_code = status.HTTP_409_CONFLICT
    return HTTPException(status_code=status_code, detail=str(exc))


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    principal: CurrentUserDep,
    session: SessionDep,
) -> ProfileResponse:
    """本人资料：含邮箱、实名、联系方式与合作记录。"""
    try:
        profile = await profile_service.get_profile(session, principal.user_id)
    except ProfileError as exc:
        raise _http_error(exc) from exc
    return _profile_response(profile)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> ProfileResponse:
    """修改昵称 / 邮箱 / 介绍 / 技能 / 城市 / 联系方式；空串表示清空可空字段。"""
    try:
        profile = await profile_service.update_profile(
            session,
            user_id=principal.user_id,
            nickname=payload.nickname,
            email=payload.email,
            bio=payload.bio,
            skills=payload.skills,
            city=payload.city,
            contact_phone=payload.contact_phone,
            contact_wechat=payload.contact_wechat,
        )
    except ProfileError as exc:
        raise _http_error(exc) from exc
    return _profile_response(profile)


@router.get(
    "/profile/certification-applications",
    response_model=CertificationApplicationListResponse,
)
async def list_my_certification_applications(
    principal: CurrentUserDep,
    session: SessionDep,
) -> CertificationApplicationListResponse:
    """我的认证申请（当前用户全部申请，最新在前）。"""
    try:
        items = await certification_service.list_my_applications(session, user_id=principal.user_id)
    except CertificationError as exc:
        raise _http_error(exc) from exc
    return CertificationApplicationListResponse(
        items=[certification_application_response(item) for item in items]
    )


@router.post(
    "/profile/certification-applications",
    response_model=CertificationApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_certification_application(
    payload: CertificationApplicationCreateRequest,
    principal: CurrentUserDep,
    session: SessionDep,
) -> CertificationApplicationResponse:
    """提交实名 / 企业 / 工程师认证申请，落 pending 待管理员审核。"""
    fields = payload.model_dump(exclude={"type"})
    try:
        item = await certification_service.create_application(
            session,
            user_id=principal.user_id,
            application_type=payload.type,
            fields=fields,
        )
    except CertificationError as exc:
        raise _http_error(exc) from exc
    return certification_application_response(item)


@router.get("/profiles/{user_id}", response_model=PublicProfileResponse)
async def get_public_profile(
    user_id: int,
    _principal: CurrentUserDep,
    session: SessionDep,
) -> PublicProfileResponse:
    """他人公开主页：昵称 / 介绍 / 技能 / 城市 / 认证 / 合作记录，隐藏敏感字段。"""
    try:
        profile = await profile_service.get_public_profile(session, user_id)
    except ProfileError as exc:
        raise _http_error(exc) from exc
    return _public_profile_response(profile)


__all__ = ["router"]
