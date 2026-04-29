from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class PaperSession(TimestampMixin, Base):
    """Represents one simulation cycle (reset-to-reset).

    Every order, position, and daily return belongs to exactly one session.
    When the user resets the account a new session is created so that historical
    records remain queryable, grouped, and comparable across cycles for LLM
    report generation.
    """
    __tablename__ = "paper_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    label: Mapped[str | None] = mapped_column(String(128))
    initial_balance: Mapped[float] = mapped_column(Float, default=1000000.0, nullable=False)
    final_balance: Mapped[float | None] = mapped_column(Float)
    total_pnl: Mapped[float | None] = mapped_column(Float)
    total_trades: Mapped[int | None] = mapped_column(Integer)
    win_rate: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)


class PaperOrder(TimestampMixin, Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("paper_sessions.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("strategy_runs.id"))
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stock_snapshots.id"))
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), nullable=False)
    strategy_name: Mapped[str | None] = mapped_column(String(64))
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    side: Mapped[str] = mapped_column(String(8), default="buy", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_price: Mapped[float | None] = mapped_column(Float)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    pnl: Mapped[float | None] = mapped_column(Float)
    return_pct: Mapped[float | None] = mapped_column(Float)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaperPosition(TimestampMixin, Base):
    __tablename__ = "paper_positions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("paper_sessions.id"), index=True)
    strategy_name: Mapped[str | None] = mapped_column(String(64))
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    average_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    pnl: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="open", nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaperDailyReturn(TimestampMixin, Base):
    __tablename__ = "paper_daily_returns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("paper_sessions.id"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Removed unique=True on trade_date — different sessions can have the same date.
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_pnl: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    strategy_name: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PaperAccount(TimestampMixin, Base):
    __tablename__ = "paper_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    active_session_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("paper_sessions.id"))
    initial_balance: Mapped[float] = mapped_column(Float, default=1000000.0, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=1000000.0, nullable=False)
