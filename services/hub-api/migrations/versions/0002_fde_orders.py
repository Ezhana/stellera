"""FDE 订单与工作日志。

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-02
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fde_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("industry", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("delivery_days", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("escrow_status", sa.String(length=16), nullable=False),
        sa.Column("publisher_id", sa.Integer(), nullable=False),
        sa.Column("engineer_id", sa.Integer(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["engineer_id"], ["users.id"], name="fk_fde_orders_engineer_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["publisher_id"], ["users.id"], name="fk_fde_orders_publisher_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fde_orders"),
    )
    op.create_index("ix_fde_orders_code", "fde_orders", ["code"], unique=True)
    op.create_index("ix_fde_orders_created_at", "fde_orders", ["created_at"], unique=False)
    op.create_index("ix_fde_orders_engineer_id", "fde_orders", ["engineer_id"], unique=False)
    op.create_index("ix_fde_orders_publisher_id", "fde_orders", ["publisher_id"], unique=False)
    op.create_index("ix_fde_orders_status", "fde_orders", ["status"], unique=False)

    op.create_table(
        "fde_order_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("worked_hours", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["fde_orders.id"],
            name="fk_fde_order_logs_order_id_fde_orders",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"], ["users.id"], name="fk_fde_order_logs_author_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fde_order_logs"),
    )
    op.create_index("ix_fde_order_logs_order_id", "fde_order_logs", ["order_id"], unique=False)
    op.create_index("ix_fde_order_logs_author_id", "fde_order_logs", ["author_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fde_order_logs_author_id", table_name="fde_order_logs")
    op.drop_index("ix_fde_order_logs_order_id", table_name="fde_order_logs")
    op.drop_table("fde_order_logs")
    op.drop_index("ix_fde_orders_status", table_name="fde_orders")
    op.drop_index("ix_fde_orders_publisher_id", table_name="fde_orders")
    op.drop_index("ix_fde_orders_engineer_id", table_name="fde_orders")
    op.drop_index("ix_fde_orders_created_at", table_name="fde_orders")
    op.drop_index("ix_fde_orders_code", table_name="fde_orders")
    op.drop_table("fde_orders")
