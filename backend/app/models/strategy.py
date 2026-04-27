from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class StrategyRun(TimestampMixin, Base):
    __tablename__ = "strategy_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    strategy_name: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)


class StrategyCandidate(TimestampMixin, Base):
    __tablename__ = "strategy_candidates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("strategy_runs.id"),
        index=True,
        nullable=False,
    )
    stock_code: Mapped[str] = mapped_column(String(16), nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
