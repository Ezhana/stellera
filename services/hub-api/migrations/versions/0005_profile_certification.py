"""个人资料字段与认证申请。

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 个人资料字段全部可空，不动已有数据；full_name 继续作为实名保留。
    op.add_column("users", sa.Column("nickname", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("bio", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("skills", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("city", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("contact_phone", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("contact_wechat", sa.String(length=64), nullable=True))

    op.create_table(
        "certification_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("real_name", sa.String(length=128), nullable=True),
        sa.Column("id_number", sa.String(length=64), nullable=True),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("credit_code", sa.String(length=64), nullable=True),
        sa.Column("contact_name", sa.String(length=64), nullable=True),
        sa.Column("skills", sa.String(length=255), nullable=True),
        sa.Column("work_years", sa.Integer(), nullable=True),
        sa.Column("project_experience", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("review_note", sa.String(length=500), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_certification_applications_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name="fk_certification_applications_reviewer_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_certification_applications"),
    )
    op.create_index(
        "ix_certification_applications_user_id",
        "certification_applications",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_certification_applications_type",
        "certification_applications",
        ["type"],
        unique=False,
    )
    op.create_index(
        "ix_certification_applications_status",
        "certification_applications",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_certification_applications_status", table_name="certification_applications")
    op.drop_index("ix_certification_applications_type", table_name="certification_applications")
    op.drop_index("ix_certification_applications_user_id", table_name="certification_applications")
    op.drop_table("certification_applications")
    op.drop_column("users", "contact_wechat")
    op.drop_column("users", "contact_phone")
    op.drop_column("users", "city")
    op.drop_column("users", "skills")
    op.drop_column("users", "bio")
    op.drop_column("users", "nickname")
