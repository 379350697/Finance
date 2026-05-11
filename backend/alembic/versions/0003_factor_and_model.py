"""add factor_caches and model_configs tables

Revision ID: 0003_factor_and_model
Revises: 0002_paper_sessions
Create Date: 2026-05-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0003_factor_and_model"
down_revision: str | None = "0002_paper_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "factor_caches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stock_code", sa.String(length=16), nullable=False),
        sa.Column("factor_set", sa.String(length=64), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_factor_caches_stock_code"), "factor_caches", ["stock_code"], unique=False)

    op.create_table(
        "model_configs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=False),
        sa.Column("model_type", sa.String(length=32), nullable=False),
        sa.Column("factor_set", sa.String(length=64), nullable=False),
        sa.Column("train_start", sa.Date(), nullable=False),
        sa.Column("train_end", sa.Date(), nullable=False),
        sa.Column("valid_start", sa.Date(), nullable=False),
        sa.Column("valid_end", sa.Date(), nullable=False),
        sa.Column("test_start", sa.Date(), nullable=False),
        sa.Column("test_end", sa.Date(), nullable=False),
        sa.Column("hyperparams", sa.JSON(), nullable=False),
        sa.Column("ic_mean", sa.Float(), nullable=True),
        sa.Column("ic_std", sa.Float(), nullable=True),
        sa.Column("icir", sa.Float(), nullable=True),
        sa.Column("rank_ic_mean", sa.Float(), nullable=True),
        sa.Column("rank_ic_std", sa.Float(), nullable=True),
        sa.Column("rank_icir", sa.Float(), nullable=True),
        sa.Column("mse", sa.Float(), nullable=True),
        sa.Column("mae", sa.Float(), nullable=True),
        sa.Column("feature_importance", sa.JSON(), nullable=False),
        sa.Column("model_path", sa.String(length=256), nullable=True),
        sa.Column("stock_count", sa.Integer(), nullable=True),
        sa.Column("label_type", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("model_name"),
    )


def downgrade() -> None:
    op.drop_table("model_configs")
    op.drop_index(op.f("ix_factor_caches_stock_code"), table_name="factor_caches")
    op.drop_table("factor_caches")
