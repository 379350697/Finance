"""add paper_sessions and session lifecycle columns

Revision ID: 0002_paper_sessions
Revises: 0001_initial_schema
Create Date: 2026-04-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_paper_sessions"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── New table: paper_sessions ─────────────────────────────────────────
    op.create_table(
        "paper_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("initial_balance", sa.Float(), nullable=False, server_default="1000000"),
        sa.Column("final_balance", sa.Float(), nullable=True),
        sa.Column("total_pnl", sa.Float(), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=True),
        sa.Column("win_rate", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── New table: paper_accounts ─────────────────────────────────────────
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("active_session_id", sa.String(length=36), nullable=True),
        sa.Column("initial_balance", sa.Float(), nullable=False, server_default="1000000"),
        sa.Column("balance", sa.Float(), nullable=False, server_default="1000000"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["active_session_id"], ["paper_sessions.id"], name="fk_paper_accounts_active_session"),
    )

    with op.batch_alter_table("paper_orders") as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("strategy_name", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_paper_orders_session_id", ["session_id"])
        batch_op.create_index("ix_paper_orders_session_status", ["session_id", "status"])
        batch_op.create_foreign_key(
            "fk_paper_orders_session", "paper_sessions", ["session_id"], ["id"]
        )

    with op.batch_alter_table("paper_positions") as batch_op:
        batch_op.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("strategy_name", sa.String(length=64), nullable=True))
        batch_op.create_index("ix_paper_positions_session_id", ["session_id"])
        batch_op.create_foreign_key(
            "fk_paper_positions_session", "paper_sessions", ["session_id"], ["id"]
        )

    with op.batch_alter_table("paper_daily_returns") as batch_op:
        # First drop the unique constraint on trade_date (different sessions can have the same date)
        batch_op.drop_constraint("uq_paper_daily_returns_trade_date", type_="unique")
        batch_op.add_column(sa.Column("session_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("strategy_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
        batch_op.create_index("ix_paper_daily_returns_session_id", ["session_id"])
        batch_op.create_index("ix_paper_daily_returns_session_date_status", ["session_id", "trade_date", "status"])
        batch_op.create_foreign_key(
            "fk_paper_daily_returns_session", "paper_sessions", ["session_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("paper_daily_returns") as batch_op:
        batch_op.drop_constraint("fk_paper_daily_returns_session", type_="foreignkey")
        batch_op.drop_index("ix_paper_daily_returns_session_date_status")
        batch_op.drop_index("ix_paper_daily_returns_session_id")
        batch_op.drop_column("status")
        batch_op.drop_column("strategy_name")
        batch_op.drop_column("session_id")
        batch_op.create_unique_constraint("uq_paper_daily_returns_trade_date", ["trade_date"])

    with op.batch_alter_table("paper_positions") as batch_op:
        batch_op.drop_constraint("fk_paper_positions_session", type_="foreignkey")
        batch_op.drop_index("ix_paper_positions_session_id")
        batch_op.drop_column("strategy_name")
        batch_op.drop_column("session_id")

    with op.batch_alter_table("paper_orders") as batch_op:
        batch_op.drop_constraint("fk_paper_orders_session", type_="foreignkey")
        batch_op.drop_index("ix_paper_orders_session_status")
        batch_op.drop_index("ix_paper_orders_session_id")
        batch_op.drop_column("strategy_name")
        batch_op.drop_column("session_id")

    op.drop_table("paper_accounts")

    op.drop_table("paper_sessions")
