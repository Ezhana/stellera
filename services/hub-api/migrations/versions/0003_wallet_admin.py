"""钱包 / 兑换码 / 系统设置。

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("balance_cents", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
            ["user_id"], ["users.id"], name="fk_wallets_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallets"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"], unique=True)

    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("wallet_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=24), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("balance_after_cents", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("reference_type", sa.String(length=24), nullable=True),
        sa.Column("reference_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["wallet_id"],
            ["wallets.id"],
            name="fk_wallet_transactions_wallet_id_wallets",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_transactions"),
    )
    op.create_index(
        "ix_wallet_transactions_wallet_id",
        "wallet_transactions",
        ["wallet_id"],
        unique=False,
    )
    op.create_index(
        "ix_wallet_transactions_type", "wallet_transactions", ["type"], unique=False
    )

    op.create_table(
        "redeem_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("batch_no", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=120), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("used_by_id", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], name="fk_redeem_codes_created_by_id_users"
        ),
        sa.ForeignKeyConstraint(
            ["used_by_id"], ["users.id"], name="fk_redeem_codes_used_by_id_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_redeem_codes"),
    )
    op.create_index("ix_redeem_codes_code", "redeem_codes", ["code"], unique=True)
    op.create_index("ix_redeem_codes_status", "redeem_codes", ["status"], unique=False)
    op.create_index("ix_redeem_codes_batch_no", "redeem_codes", ["batch_no"], unique=False)
    op.create_index("ix_redeem_codes_used_by_id", "redeem_codes", ["used_by_id"], unique=False)

    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"], ["users.id"], name="fk_system_settings_updated_by_id_users"
        ),
        sa.PrimaryKeyConstraint("key", name="pk_system_settings"),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index("ix_redeem_codes_used_by_id", table_name="redeem_codes")
    op.drop_index("ix_redeem_codes_batch_no", table_name="redeem_codes")
    op.drop_index("ix_redeem_codes_status", table_name="redeem_codes")
    op.drop_index("ix_redeem_codes_code", table_name="redeem_codes")
    op.drop_table("redeem_codes")
    op.drop_index("ix_wallet_transactions_type", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_wallet_id", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")
    op.drop_index("ix_wallets_user_id", table_name="wallets")
    op.drop_table("wallets")
