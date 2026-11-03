"""FDE 接单 / 交付申请。

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fde_order_applications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
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
            ["order_id"],
            ["fde_orders.id"],
            name="fk_fde_order_applications_order_id_fde_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["users.id"],
            name="fk_fde_order_applications_applicant_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id"],
            ["users.id"],
            name="fk_fde_order_applications_reviewer_id_users",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fde_order_applications"),
    )
    op.create_index(
        "ix_fde_order_applications_order_id",
        "fde_order_applications",
        ["order_id"],
        unique=False,
    )
    op.create_index(
        "ix_fde_order_applications_applicant_id",
        "fde_order_applications",
        ["applicant_id"],
        unique=False,
    )
    op.create_index(
        "ix_fde_order_applications_type", "fde_order_applications", ["type"], unique=False
    )
    op.create_index(
        "ix_fde_order_applications_status", "fde_order_applications", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_fde_order_applications_status", table_name="fde_order_applications")
    op.drop_index("ix_fde_order_applications_type", table_name="fde_order_applications")
    op.drop_index("ix_fde_order_applications_applicant_id", table_name="fde_order_applications")
    op.drop_index("ix_fde_order_applications_order_id", table_name="fde_order_applications")
    op.drop_table("fde_order_applications")
