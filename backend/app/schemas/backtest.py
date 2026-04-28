from datetime import date

from pydantic import BaseModel, Field

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
