"""Pydantic schemas for factor computation and model training/prediction."""

from datetime import date

from pydantic import BaseModel, Field


# ── Factor ──────────────────────────────────────────────────────────────────────

class FactorComputeRequest(BaseModel):
    codes: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date
    factor_set: str = "alpha158"


class FactorComputeResponse(BaseModel):
    codes_count: int
    factor_count: int
    date_range: tuple[date, date]
    factor_names: list[str]
    status: str


# ── Model Training ──────────────────────────────────────────────────────────────

class ModelTrainRequest(BaseModel):
    model_name: str
    factor_set: str = "alpha158"
    train_start: date
    train_end: date
    valid_start: date
    valid_end: date
    test_start: date
    test_end: date
    stock_pool: list[str] = Field(default_factory=list)
    model_type: str = "lightgbm"
    label_type: str = "next_ret5"
    hyperparams: dict = Field(default_factory=dict)


class ModelTrainResponse(BaseModel):
    model_name: str
    model_type: str
    factor_set: str
    ic_mean: float
    ic_std: float
    icir: float
    rank_ic_mean: float
    rank_ic_std: float
    rank_icir: float
    mse: float
    mae: float
    feature_importance: dict[str, float]
    status: str


# ── Model Prediction ────────────────────────────────────────────────────────────

class ModelPredictRequest(BaseModel):
    model_name: str
    codes: list[str] = Field(default_factory=list)
    predict_date: date


class StockScore(BaseModel):
    code: str
    score: float
    rank: int


class ModelPredictResponse(BaseModel):
    predictions: list[StockScore]


# ── IC Analysis (shared) ────────────────────────────────────────────────────────

class ICPoint(BaseModel):
    date: date
    ic: float
    rank_ic: float


class ICAnalysisSummary(BaseModel):
    ic_mean: float
    ic_std: float
    icir: float
    rank_ic_mean: float
    rank_ic_std: float
    rank_icir: float
    ic_series: list[ICPoint] = Field(default_factory=list)
