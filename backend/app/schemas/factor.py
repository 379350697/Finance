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
    model_type: str = "lightgbm"


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


# ── Model Comparison ──────────────────────────────────────────────────────────────

class ModelCompareRequest(BaseModel):
    model_name_prefix: str
    factor_set: str = "alpha158"
    train_start: date
    train_end: date
    valid_start: date
    valid_end: date
    test_start: date
    test_end: date
    stock_pool: list[str] = Field(default_factory=list)
    label_type: str = "next_ret5"
    model_types: list[str] = Field(
        default_factory=lambda: ["lightgbm", "xgboost", "catboost", "mlp"]
    )
    hyperparams: dict = Field(default_factory=dict)


class ModelCompareItem(BaseModel):
    model_type: str
    ic_mean: float = 0.0
    ic_std: float = 0.0
    icir: float = 0.0
    rank_ic_mean: float = 0.0
    rank_icir: float = 0.0
    mse: float = 0.0
    mae: float = 0.0
    train_time_seconds: float = 0.0
    status: str = "completed"


class ModelCompareResponse(BaseModel):
    comparison: list[ModelCompareItem]
    best_model: str = ""  # model_type with highest ICIR among completed runs


# ── Rolling Retraining ──────────────────────────────────────────────────────────

class RollingTrainRequest(BaseModel):
    base_model_name: str
    model_type: str = "lightgbm"
    factor_set: str = "alpha158"
    stock_pool: list[str] = Field(default_factory=list)
    label_type: str = "next_ret5"
    window_days: int = 252
    step_days: int = 21
    min_train_days: int = 120
    start_date: date | None = None
    end_date: date | None = None
    hyperparams: dict = Field(default_factory=dict)


class WindowResultSchema(BaseModel):
    window_index: int
    train_start: date
    train_end: date
    valid_start: date
    valid_end: date
    test_start: date
    test_end: date
    ic_mean: float = 0.0
    icir: float = 0.0
    rank_ic_mean: float = 0.0
    rank_icir: float = 0.0
    model_path: str = ""


class RollingTrainResponse(BaseModel):
    windows: list[WindowResultSchema]
    ic_decay_trend: float = 0.0  # slope of IC across windows (negative = decay)
    model_type: str = ""
    factor_set: str = ""
    total_windows: int = 0
