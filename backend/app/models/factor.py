from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._mixins import TimestampMixin, new_uuid


class FactorCache(TimestampMixin, Base):
    """Cached factor data per stock and factor set for a date range."""

    __tablename__ = "factor_caches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    stock_code: Mapped[str] = mapped_column(String(16), index=True, nullable=False)
    factor_set: Mapped[str] = mapped_column(String(64), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class ModelConfig(TimestampMixin, Base):
    """Trained model metadata and evaluation metrics."""

    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    model_name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    model_type: Mapped[str] = mapped_column(String(32), nullable=False)
    factor_set: Mapped[str] = mapped_column(String(64), nullable=False)
    train_start: Mapped[date] = mapped_column(Date, nullable=False)
    train_end: Mapped[date] = mapped_column(Date, nullable=False)
    valid_start: Mapped[date] = mapped_column(Date, nullable=False)
    valid_end: Mapped[date] = mapped_column(Date, nullable=False)
    test_start: Mapped[date] = mapped_column(Date, nullable=False)
    test_end: Mapped[date] = mapped_column(Date, nullable=False)
    hyperparams: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    ic_mean: Mapped[float | None] = mapped_column(Float)
    ic_std: Mapped[float | None] = mapped_column(Float)
    icir: Mapped[float | None] = mapped_column(Float)
    rank_ic_mean: Mapped[float | None] = mapped_column(Float)
    rank_ic_std: Mapped[float | None] = mapped_column(Float)
    rank_icir: Mapped[float | None] = mapped_column(Float)
    mse: Mapped[float | None] = mapped_column(Float)
    mae: Mapped[float | None] = mapped_column(Float)
    feature_importance: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    model_path: Mapped[str | None] = mapped_column(String(256))
    stock_count: Mapped[int | None] = mapped_column(Integer)
    label_type: Mapped[str | None] = mapped_column(String(32))
