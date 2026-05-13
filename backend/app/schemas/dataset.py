"""Dataset configuration schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SegmentConfig(BaseModel):
    """Date range for one dataset segment (train/valid/test)."""

    start: date
    end: date


class DatasetConfig(BaseModel):
    """Configuration for DataHandlerLP pipeline."""

    factor_set: str = "alpha158"
    label_type: str = "next_ret5"
    stock_pool: list[str] = Field(default_factory=list)

    # Processor pipeline configuration
    processor_pipeline: list[str] = Field(
        default_factory=lambda: ["fillna", "zscore"]
    )
    # Supported pipeline step names: fillna, zscore, rank_norm, minmax, cszscore

    # Segment date ranges
    train_seg: SegmentConfig
    valid_seg: SegmentConfig | None = None
    test_seg: SegmentConfig

    model_config = {"arbitrary_types_allowed": True}
