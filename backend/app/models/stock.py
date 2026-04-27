from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin


class Stock(TimestampMixin, Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    market: Mapped[str | None] = mapped_column(String(16))
    exchange: Mapped[str | None] = mapped_column(String(16))
    industry: Mapped[str | None] = mapped_column(String(64))
    listed_date: Mapped[date | None] = mapped_column(Date)
