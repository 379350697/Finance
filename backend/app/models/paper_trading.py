from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class PaperOrder(TimestampMixin, Base):
    __tablename__ = "paper_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("strategy_runs.id"))
    snapshot_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("stock_snapshots.id"))
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), nullable=False)
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
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    win_rate: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    total_pnl: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    return_pct: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PaperAccount(TimestampMixin, Base):
    __tablename__ = "paper_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    initial_balance: Mapped[float] = mapped_column(Float, default=1000000.0, nullable=False)
    balance: Mapped[float] = mapped_column(Float, default=1000000.0, nullable=False)
