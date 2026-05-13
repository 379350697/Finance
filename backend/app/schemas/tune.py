"""Hyperparameter tuning schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class TuneConfig(BaseModel):
    """Configuration for a hyperparameter tuning study."""

    study_name: str = "tune"
    model_type: str = "lightgbm"
    factor_set: str = "alpha158"
    train_start: date
    train_end: date
    valid_start: date
    valid_end: date
    test_start: date
    test_end: date
    stock_pool: list[str] = Field(default_factory=list)
    label_type: str = "next_ret5"
    n_trials: int = 20
    cv_folds: int = 3
    direction: str = "maximize"  # maximize ICIR


class TrialResultSchema(BaseModel):
    """Result for a single tuning trial."""

    trial_id: int
    params: dict[str, float | int | str]
    ic_mean: float = 0.0
    icir: float = 0.0
    rank_ic_mean: float = 0.0
    rank_icir: float = 0.0


class TuneResultSchema(BaseModel):
    """Aggregate result from a tuning study."""

    study_name: str
    model_type: str
    best_params: dict[str, float | int | str]
    best_icir: float = 0.0
    trials: list[TrialResultSchema] = Field(default_factory=list)
