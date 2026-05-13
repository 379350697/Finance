from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from app.schemas.factor import ICAnalysisSummary
from app.schemas.market import DailyBar


class BacktestStockBars(BaseModel):
    code: str
    name: str | None = None
    bars: list[DailyBar]
    context: dict = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    strategy_name: str
    start_date: date
    end_date: date
    stock_pool: list[str] = Field(default_factory=list)
    stocks: list[BacktestStockBars] = Field(default_factory=list)
    initial_capital: float = 100_000
    position_size: float = 10_000
    holding_days: int = 1
    strategy_params: dict = Field(default_factory=dict)
    use_exchange_sim: bool = False
    use_execution_sim: bool = False
    enable_ic_analysis: bool = False
    enable_attribution: bool = False
    portfolio_method: str = "equal_weight"  # equal_weight, risk_parity, mean_variance, max_sharpe, min_variance
    portfolio_constraints: dict = Field(default_factory=dict)
    order_generator: str | None = None  # "with_interact" / "without_interact"


class AttributionEffect(BaseModel):
    name: str
    value: float  # contribution to excess return (decimal)
    pct: float    # as percentage of total


class BrinsonResult(BaseModel):
    allocation_effects: list[AttributionEffect] = Field(default_factory=list)
    selection_effects: list[AttributionEffect] = Field(default_factory=list)
    interaction_effects: list[AttributionEffect] = Field(default_factory=list)
    total_excess: float = 0.0


class FactorAttributionResult(BaseModel):
    factor_contributions: list[AttributionEffect] = Field(default_factory=list)
    residual: AttributionEffect | None = None
    total_return: float = 0.0


class AttributionResult(BaseModel):
    brinson: BrinsonResult | None = None
    factor: FactorAttributionResult | None = None


class BacktestTrade(BaseModel):
    stock_code: str
    stock_name: str | None = None
    strategy_name: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    return_pct: float
    signal_score: float = 0
    signal_reason: str
    metrics: dict = Field(default_factory=dict)


class BacktestDailyReturn(BaseModel):
    trade_date: date
    pnl: float
    return_pct: float
    cumulative_return_pct: float
    trades: int


class BacktestResult(BaseModel):
    strategy_name: str
    start_date: date
    end_date: date
    stock_pool: list[str]
    initial_capital: float
    position_size: float
    trade_count: int
    win_rate: float
    total_return_pct: float
    max_drawdown_pct: float
    trades: list[BacktestTrade]
    daily_returns: list[BacktestDailyReturn]
    annualized_return: float = 0
    sharpe_ratio: float = 0
    information_ratio: float = 0
    max_drawdown_duration: int = 0
    turnover_rate: float = 0
    hit_rate: float = 0
    ic_summary: ICAnalysisSummary | None = None
    attribution: AttributionResult | None = None


# ── Portfolio Optimization Schemas ──────────────────────────────

class Order(BaseModel):
    """A single order generated during backtest."""
    code: str
    date: date
    direction: str  # "buy" or "sell"
    quantity: float
    price_limit: float | None = None
    signal_score: float = 0.0
    reason: str = ""


class PortfolioOptRequest(BaseModel):
    codes: list[str]
    start_date: date
    end_date: date
    method: str = "equal_weight"
    constraints: dict = Field(default_factory=dict)
    scores: dict[str, float] | None = None


class FrontierPoint(BaseModel):
    volatility: float
    expected_return: float
    sharpe_ratio: float
    weights: list[float]


class PortfolioOptResult(BaseModel):
    weights: dict[str, float]
    expected_return: float
    expected_volatility: float
    sharpe_ratio: float
    efficient_frontier: list[FrontierPoint] = []
