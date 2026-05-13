from fastapi import APIRouter

from app.schemas.backtest import (
    BacktestRequest,
    BacktestResult,
    PortfolioOptRequest,
    PortfolioOptResult,
    FrontierPoint,
)
from app.services.backtest import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run")
def run_backtest(request: BacktestRequest) -> BacktestResult:
    return BacktestService().run(request)


@router.post("/optimize", response_model=PortfolioOptResult)
def optimize_portfolio(req: PortfolioOptRequest) -> PortfolioOptResult:
    import numpy as np
    import pandas as pd

    from app.services.backtest.portfolio_optimizer import PortfolioOptimizer
    from app.services.data.service import MarketDataService

    market = MarketDataService()
    all_returns: dict = {}
    for code in req.codes:
        bars = market.get_daily_bars(code, req.start_date, req.end_date)
        if bars:
            closes = [{"date": b.trade_date, code: b.close} for b in bars if b.close > 0]
            df = pd.DataFrame(closes).set_index("date").sort_index()
            all_returns[code] = df[code].pct_change().dropna()

    returns_df = pd.DataFrame(all_returns).dropna(axis=1, thresh=5)
    if returns_df.shape[1] < 2:
        return PortfolioOptResult(
            weights={code: round(1.0 / len(req.codes), 6) for code in req.codes},
            expected_return=0.0,
            expected_volatility=0.0,
            sharpe_ratio=0.0,
            efficient_frontier=[],
        )

    scores_df = None
    if req.scores:
        scores_df = pd.DataFrame([req.scores], index=[returns_df.index[-1]])

    optimizer = PortfolioOptimizer(method=req.method, constraints=req.constraints)
    weights_arr = optimizer.optimize(returns_df, scores_df)
    frontier = optimizer.efficient_frontier(returns_df)

    valid_codes = returns_df.columns.tolist()
    weights = {code: round(float(w), 6) for code, w in zip(valid_codes, weights_arr)}

    mu = returns_df.mean().values
    cov = returns_df.cov().values
    w = np.array(list(weights.values()))
    exp_ret = float(w @ mu) * 252
    exp_vol = float(np.sqrt(w @ cov @ w)) * np.sqrt(252)
    sharpe = exp_ret / exp_vol if exp_vol > 0 else 0.0

    return PortfolioOptResult(
        weights=weights,
        expected_return=round(exp_ret, 6),
        expected_volatility=round(exp_vol, 6),
        sharpe_ratio=round(sharpe, 6),
        efficient_frontier=[FrontierPoint(**fp) for fp in frontier],
    )
