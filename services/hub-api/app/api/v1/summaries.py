"""用户摘要与认证申请响应构造：多个端点共用，保证字段结构一致。

用户摘要统一为 `{id, display_name, certifications}`；展示名取昵称
（nickname → full_name → username），认证列表由角色派生且顺序固定。
"""

from __future__ import annotations

from typing import cast

from app.models.base import ensure_utc
from app.models.user import User
from app.schemas.fde import OrderUserRef
from app.schemas.profile import (
    CertificationApplicationResponse,
    CertificationStatus,
    CertificationType,
)
from app.services.certification import (
    CertificationApplicationItem,
    certifications_from_roles,
    display_name,
)


def user_ref(user: User) -> OrderUserRef:
    return OrderUserRef(
        id=user.id,
        display_name=display_name(user),
        certifications=list(certifications_from_roles(role.name for role in user.roles)),
    )


def certification_application_response(
    item: CertificationApplicationItem,
) -> CertificationApplicationResponse:
    application = item.application
    return CertificationApplicationResponse(
        id=application.id,
        type=cast(CertificationType, application.type),
        status=cast(CertificationStatus, application.status),
        real_name=application.real_name,
        id_number=application.id_number,
        contact_phone=application.contact_phone,
        company_name=application.company_name,
        credit_code=application.credit_code,
        contact_name=application.contact_name,
        skills=application.skills,
        work_years=application.work_years,
        project_experience=application.project_experience,
        description=application.description,
        review_note=application.review_note,
        reviewer=user_ref(application.reviewer) if application.reviewer is not None else None,
        reviewed_at=(
            ensure_utc(application.reviewed_at) if application.reviewed_at is not None else None
        ),
        created_at=ensure_utc(application.created_at),
    )


__all__ = ["certification_application_response", "user_ref"]
