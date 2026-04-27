from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class StockSnapshot(TimestampMixin, Base):
    __tablename__ = "stock_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("strategy_runs.id"))
    candidate_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("strategy_candidates.id"),
    )
    stock_code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    stock_name: Mapped[str] = mapped_column(String(64), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    quote_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    indicator_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    strategy_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    news_data: Mapped[dict | None] = mapped_column(JSON)
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
