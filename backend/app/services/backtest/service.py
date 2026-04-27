from collections import defaultdict

from app.schemas.backtest import (
    BacktestDailyReturn,
    BacktestRequest,
    BacktestResult,
    BacktestStockBars,
    BacktestTrade,
)
from app.schemas.market import DailyBar
from app.services.strategy.registry import StrategyRegistry, default_strategy_registry


class BacktestService:
    def __init__(self, registry: StrategyRegistry | None = None):
        self.registry = registry or default_strategy_registry()

    def run(self, request: BacktestRequest) -> BacktestResult:
        strategy = self.registry.get(request.strategy_name)
        trades: list[BacktestTrade] = []
        stock_pool = set(request.stock_pool)

        for stock in request.stocks:
            if stock_pool and stock.code not in stock_pool:
                continue
            trades.extend(self._run_stock(request, stock))

        trades.sort(key=lambda trade: (trade.exit_date, trade.stock_code, trade.entry_date))
        daily_returns = self._build_daily_returns(trades, request.initial_capital)
        total_pnl = sum(trade.pnl for trade in trades)
        winning_trades = sum(1 for trade in trades if trade.pnl > 0)
        win_rate = round(winning_trades / len(trades), 4) if trades else 0

        return BacktestResult(
            strategy_name=strategy.name,
            start_date=request.start_date,
            end_date=request.end_date,
            stock_pool=request.stock_pool,
            initial_capital=request.initial_capital,
            position_size=request.position_size,
            trade_count=len(trades),
            win_rate=win_rate,
            total_return_pct=round((total_pnl / request.initial_capital) * 100, 2)
            if request.initial_capital
            else 0,
            max_drawdown_pct=self._max_drawdown(daily_returns),
            trades=trades,
            daily_returns=daily_returns,
        )

    def _run_stock(self, request: BacktestRequest, stock: BacktestStockBars) -> list[BacktestTrade]:
        strategy = self.registry.get(request.strategy_name)
        bars = sorted(stock.bars, key=lambda bar: bar.trade_date)
        trades: list[BacktestTrade] = []
        holding_days = max(request.holding_days, 1)

        for index, bar in enumerate(bars):
            exit_index = index + holding_days
            if exit_index >= len(bars):
                continue
            if bar.trade_date < request.start_date or bar.trade_date > request.end_date:
                continue

            history = bars[: index + 1]
            context = self._build_context(stock.context, request.strategy_params, bars, index)
            signal = strategy.evaluate(stock.code, history, context=context)
            if not signal.matched:
                continue

            exit_bar = bars[exit_index]
            quantity = request.position_size / bar.close if bar.close else 0
            pnl = (exit_bar.close - bar.close) * quantity
            return_pct = ((exit_bar.close - bar.close) / bar.close) * 100 if bar.close else 0
            trades.append(
                BacktestTrade(
                    stock_code=stock.code,
                    stock_name=stock.name,
                    strategy_name=strategy.name,
                    entry_date=bar.trade_date,
                    exit_date=exit_bar.trade_date,
                    entry_price=round(bar.close, 4),
                    exit_price=round(exit_bar.close, 4),
                    quantity=round(quantity, 4),
                    pnl=round(pnl, 2),
                    return_pct=round(return_pct, 2),
                    signal_score=signal.score,
                    signal_reason=signal.reason,
                    metrics=signal.metrics,
                )
            )

        return trades

    def _build_context(
        self,
        stock_context: dict,
        strategy_params: dict,
        bars: list[DailyBar],
        index: int,
    ) -> dict:
        bar = bars[index]
        previous = bars[index - 1] if index > 0 else None
        previous_volumes = [item.volume or 0 for item in bars[max(0, index - 5) : index]]
        avg_volume = sum(previous_volumes) / len(previous_volumes) if previous_volumes else 0
        volume_ratio = ((bar.volume or 0) / avg_volume) if avg_volume else 0

        context = {**stock_context, **strategy_params}
        context.setdefault("intraday", {})
        context["intraday"] = {
            **context["intraday"],
            "latest_price": bar.close,
            "previous_close": previous.close if previous else bar.open,
            "volume_ratio": volume_ratio,
            "large_order_inflow": context["intraday"].get("large_order_inflow", 0),
        }
        return context

    def _build_daily_returns(
        self,
        trades: list[BacktestTrade],
        initial_capital: float,
    ) -> list[BacktestDailyReturn]:
        pnl_by_date: dict = defaultdict(float)
        count_by_date: dict = defaultdict(int)
        for trade in trades:
            pnl_by_date[trade.exit_date] += trade.pnl
            count_by_date[trade.exit_date] += 1

        cumulative_pnl = 0.0
        daily_returns: list[BacktestDailyReturn] = []
        for trade_date in sorted(pnl_by_date):
            pnl = pnl_by_date[trade_date]
            cumulative_pnl += pnl
            daily_returns.append(
                BacktestDailyReturn(
                    trade_date=trade_date,
                    pnl=round(pnl, 2),
                    return_pct=round((pnl / initial_capital) * 100, 2) if initial_capital else 0,
                    cumulative_return_pct=round((cumulative_pnl / initial_capital) * 100, 2)
                    if initial_capital
                    else 0,
                    trades=count_by_date[trade_date],
                )
            )
        return daily_returns

    def _max_drawdown(self, daily_returns: list[BacktestDailyReturn]) -> float:
        peak = 0.0
        max_drawdown = 0.0
        for daily_return in daily_returns:
            equity_return = daily_return.cumulative_return_pct
            peak = max(peak, equity_return)
            max_drawdown = min(max_drawdown, equity_return - peak)
        return round(abs(max_drawdown), 2)
