from __future__ import annotations

from datetime import date

from sqlalchemy import JSON, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class LlmReport(TimestampMixin, Base):
    __tablename__ = "llm_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    period_type: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    suggestions: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), default="openai_codex", nullable=False)
    model: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="generated", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
