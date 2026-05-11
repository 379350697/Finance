from collections import defaultdict
from datetime import date, timedelta
import random

from app.schemas.backtest import (
    BacktestDailyReturn,
    BacktestRequest,
    BacktestResult,
    BacktestStockBars,
    BacktestTrade,
)
from app.schemas.market import DailyBar
from app.services.backtest.analysis import BacktestAnalyzer
from app.services.backtest.exchange_sim import ExchangeSimulator
from app.services.backtest.execution_sim import ExecutionSimulator
from app.services.data.service import MarketDataService
from app.services.strategy.registry import StrategyRegistry, default_strategy_registry

import pandas as pd


class BacktestService:
    def __init__(
        self,
        registry: StrategyRegistry | None = None,
        market_data: MarketDataService | None = None,
        factor_engine: object | None = None,
        predictor: object | None = None,
    ):
        self.registry = registry or default_strategy_registry()
        self.market_data = market_data or MarketDataService()
        self._factor_engine = factor_engine
        self._predictor = predictor

    # ------------------------------------------------------------------
    # Public: run
    # ------------------------------------------------------------------

    def run(self, request: BacktestRequest) -> BacktestResult:
        strategy = self.registry.get(request.strategy_name)

        # Decide which path to take.
        use_enhanced = (
            request.use_exchange_sim
            or request.use_execution_sim
            or request.enable_ic_analysis
            or strategy.name == "topk_dropout"
        )

        if not use_enhanced:
            return self._run_legacy(request)

        return self._run_enhanced(request)

    # ------------------------------------------------------------------
    # Legacy path (backward-compatible, identical to original)
    # ------------------------------------------------------------------

    def _run_legacy(self, request: BacktestRequest) -> BacktestResult:
        strategy = self.registry.get(request.strategy_name)
        trades: list[BacktestTrade] = []
        stock_pool = set(request.stock_pool)

        stocks = request.stocks
        if not stocks and stock_pool:
            fetch_start = request.start_date - timedelta(days=120)
            for code in stock_pool:
                try:
                    bars = self.market_data.get_daily_bars(code, fetch_start, request.end_date)
                    stocks.append(BacktestStockBars(code=code, bars=bars))
                except Exception:
                    continue

        for stock in stocks:
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

    # ------------------------------------------------------------------
    # Enhanced path
    # ------------------------------------------------------------------

    def _run_enhanced(self, request: BacktestRequest) -> BacktestResult:  # noqa: C901
        strategy = self.registry.get(request.strategy_name)
        stock_pool = set(request.stock_pool)
        initial_capital = request.initial_capital
        position_size = request.position_size
        start_date = request.start_date
        end_date = request.end_date

        # Use strategy's holding_days if available, otherwise request default
        effective_holding_days = getattr(strategy, "holding_days", None) or request.holding_days

        # ── 1. Gather bars for all pool codes ──────────────────────────
        stocks: list[BacktestStockBars] = list(request.stocks)
        loaded_codes: set[str] = {s.code for s in stocks}

        if stock_pool:
            for code in stock_pool - loaded_codes:
                try:
                    bars = self.market_data.get_daily_bars(
                        code, start_date - timedelta(days=60), end_date
                    )
                    if bars:
                        stocks.append(BacktestStockBars(code=code, bars=bars))
                except Exception:
                    continue

        # Deduplicate
        seen: set[str] = set()
        unique_stocks: list[BacktestStockBars] = []
        for s in stocks:
            if s.code not in seen:
                seen.add(s.code)
                unique_stocks.append(s)
        stocks = unique_stocks

        # ── 2. Build bars_dict for simulator lookups ───────────────────
        bars_dict: dict[str, list[DailyBar]] = {}
        for s in stocks:
            sorted_bars = sorted(s.bars, key=lambda b: b.trade_date)
            bars_dict[s.code] = sorted_bars

        # ── 3. Build trading date universe ─────────────────────────────
        all_dates: set[date] = set()
        for bars in bars_dict.values():
            for bar in bars:
                if start_date <= bar.trade_date <= end_date:
                    all_dates.add(bar.trade_date)
        trading_dates = sorted(all_dates)

        # ── 4. Optionally create simulators ────────────────────────────
        exchange_sim: ExchangeSimulator | None = None
        if request.use_exchange_sim:
            exchange_sim = ExchangeSimulator(bars_dict)

        execution_sim: ExecutionSimulator | None = None
        if request.use_execution_sim:
            execution_sim = ExecutionSimulator()

        # ── 5. Precompute rankings for TopkDropoutStrategy ─────────────
        daily_rankings: dict[date, object] = {}
        if strategy.name == "topk_dropout":
            all_codes = [s.code for s in stocks]
            try:
                daily_rankings = strategy.precompute_rankings(all_codes, trading_dates)
            except Exception:
                daily_rankings = {}

        # ── 6. Iterate trading days ────────────────────────────────────
        trades: list[BacktestTrade] = []
        positions: dict[str, dict] = {}  # code -> {entry_date, entry_price, qty, hold_days, entry_bar_date}
        position_holds: dict[str, int] = {}  # code -> days held so far
        daily_pnl: dict[date, float] = defaultdict(float)

        # Track attempted/filled for hit rate
        attempted_buys = 0
        filled_buys = 0

        # Track daily scores for IC analysis
        daily_scores: dict[date, dict[str, float]] = defaultdict(dict)
        daily_close_prices: dict[date, dict[str, float]] = defaultdict(dict)

        for di, dt in enumerate(trading_dates):
            # -- Exit positions that reached holding_days or dropped out --
            to_exit: list[str] = []
            for code, pos in list(positions.items()):
                pos["hold_days"] += 1
                position_holds[code] = pos["hold_days"]

                # Check max holding days
                if pos["hold_days"] >= effective_holding_days:
                    to_exit.append(code)
                    continue

                # Check dropout for TopkDropoutStrategy
                if strategy.name == "topk_dropout":
                    rankings = daily_rankings.get(dt)
                    if rankings is not None and not rankings.empty:
                        match = rankings.loc[rankings["code"] == code]
                        if not match.empty:
                            current_rank = int(match.iloc[0]["rank"])
                            if strategy.should_dropout(code, current_rank):
                                to_exit.append(code)

            for code in to_exit:
                pos = positions.pop(code)
                position_holds.pop(code, None)

                exit_bar = self._get_bar(bars_dict, code, dt)
                if exit_bar is None:
                    continue

                exit_qty = pos["qty"]
                desired_exit = exit_bar.open

                # Apply exchange sim if enabled
                if exchange_sim is not None:
                    fill = exchange_sim.get_fill_price(code, dt, "sell", desired_exit)
                    if fill is None:
                        continue
                    desired_exit = fill

                # Compute avg_vol for execution sim
                avg_vol = self._avg_volume(bars_dict, code, dt, window=20)

                # Apply execution sim
                exit_price = desired_exit
                if execution_sim is not None:
                    exit_price = execution_sim.exit_price(desired_exit, exit_qty, avg_vol)

                pnl = (exit_price - pos["entry_price"]) * exit_qty
                if execution_sim is not None:
                    cost = execution_sim.transaction_cost(exit_price, exit_qty, "sell")
                    pnl -= cost

                return_pct = (
                    ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
                    if pos["entry_price"]
                    else 0
                )

                daily_pnl[dt] += pnl

                trades.append(
                    BacktestTrade(
                        stock_code=code,
                        stock_name=pos.get("stock_name"),
                        strategy_name=strategy.name,
                        entry_date=pos["entry_date"],
                        exit_date=dt,
                        entry_price=round(pos["entry_price"], 4),
                        exit_price=round(exit_price, 4),
                        quantity=round(exit_qty, 4),
                        pnl=round(pnl, 2),
                        return_pct=round(return_pct, 2),
                        signal_score=pos.get("signal_score", 0),
                        signal_reason=pos.get("signal_reason", ""),
                        metrics=pos.get("metrics", {}),
                    )
                )

            # -- Evaluate new entries --
            rankings_df = daily_rankings.get(dt)
            for stock in stocks:
                code = stock.code

                # Already in a position
                if code in positions:
                    continue

                # Get bars up to today
                bar_list = bars_dict.get(code, [])
                if not bar_list:
                    continue

                # Get today's bar
                today_bar = self._get_bar(bars_dict, code, dt)
                if today_bar is None:
                    continue

                # Exchange sim: can_trade check
                if exchange_sim is not None and not exchange_sim.can_trade(code, dt):
                    continue

                # Build context for strategy evaluation
                history = [b for b in bar_list if b.trade_date <= dt]
                context = self._build_context(
                    stock.context, request.strategy_params, history, len(history) - 1
                )
                context["predict_date"] = dt

                if strategy.name == "topk_dropout":
                    context["daily_rankings"] = rankings_df
                    context["position_holds"] = position_holds

                # Evaluate
                try:
                    signal = strategy.evaluate(code, history, context=context)
                except Exception:
                    continue

                if not signal.matched:
                    # Still record scores for IC analysis
                    if signal.score:
                        daily_scores[dt][code] = signal.score
                    daily_close_prices[dt][code] = today_bar.close
                    continue

                # Prepare to enter
                attempted_buys += 1

                # Next bar index for entry
                next_idx = di + 1
                if next_idx >= len(trading_dates):
                    continue
                entry_dt = trading_dates[next_idx]

                entry_bar = self._get_bar(bars_dict, code, entry_dt)
                if entry_bar is None:
                    continue

                # Exchange sim checks
                if exchange_sim is not None:
                    if not exchange_sim.can_trade(code, entry_dt):
                        continue
                    fill = exchange_sim.get_fill_price(code, entry_dt, "buy", entry_bar.open)
                    if fill is None:
                        continue
                    desired_entry = fill
                else:
                    desired_entry = entry_bar.open

                # Compute avg_vol for execution sim
                avg_vol = self._avg_volume(bars_dict, code, entry_dt, window=20)

                # Apply execution sim
                entry_price = desired_entry
                if execution_sim is not None:
                    entry_price = execution_sim.entry_price(desired_entry, position_size / max(desired_entry, 0.001), avg_vol)

                quantity = position_size / entry_price if entry_price else 0
                if quantity <= 0:
                    continue

                # Transaction cost on entry
                if execution_sim is not None:
                    cost = execution_sim.transaction_cost(entry_price, quantity, "buy")
                    daily_pnl[entry_dt] -= cost

                positions[code] = {
                    "entry_date": entry_dt,
                    "entry_price": entry_price,
                    "qty": quantity,
                    "hold_days": 0,
                    "stock_name": stock.name,
                    "signal_score": signal.score,
                    "signal_reason": signal.reason,
                    "metrics": signal.metrics,
                }
                filled_buys += 1

                # Record score for IC analysis
                daily_scores[dt][code] = signal.score
                daily_close_prices[dt][code] = today_bar.close

            # Record close prices and scores for non-entered stocks too
            for stock in stocks:
                code = stock.code
                if code not in daily_scores.get(dt, {}):
                    today_bar = self._get_bar(bars_dict, code, dt)
                    if today_bar is not None:
                        daily_close_prices[dt][code] = today_bar.close

        # ── 7. Force-close remaining positions at last date ─────────────
        last_date = trading_dates[-1] if trading_dates else end_date
        for code, pos in list(positions.items()):
            exit_bar = self._get_bar(bars_dict, code, last_date)
            if exit_bar is None:
                continue

            desired_exit = exit_bar.close
            if exchange_sim is not None:
                fill = exchange_sim.get_fill_price(code, last_date, "sell", desired_exit)
                if fill is not None:
                    desired_exit = fill

            exit_price = desired_exit
            if execution_sim is not None:
                exit_price = execution_sim.exit_price(desired_exit, pos["qty"], 0)

            pnl = (exit_price - pos["entry_price"]) * pos["qty"]
            if execution_sim is not None:
                cost = execution_sim.transaction_cost(exit_price, pos["qty"], "sell")
                pnl -= cost

            return_pct = (
                ((exit_price - pos["entry_price"]) / pos["entry_price"]) * 100
                if pos["entry_price"]
                else 0
            )

            daily_pnl[last_date] += pnl
            trades.append(
                BacktestTrade(
                    stock_code=code,
                    stock_name=pos.get("stock_name"),
                    strategy_name=strategy.name,
                    entry_date=pos["entry_date"],
                    exit_date=last_date,
                    entry_price=round(pos["entry_price"], 4),
                    exit_price=round(exit_price, 4),
                    quantity=round(pos["qty"], 4),
                    pnl=round(pnl, 2),
                    return_pct=round(return_pct, 2),
                    signal_score=pos.get("signal_score", 0),
                    signal_reason=pos.get("signal_reason", ""),
                    metrics=pos.get("metrics", {}),
                )
            )

        # ── 8. Build daily returns ──────────────────────────────────────
        trades.sort(key=lambda t: (t.exit_date, t.stock_code, t.entry_date))
        daily_returns = self._build_daily_returns(trades, initial_capital)
        total_pnl = sum(t.pnl for t in trades)
        winning_trades = sum(1 for t in trades if t.pnl > 0)
        win_rate = round(winning_trades / len(trades), 4) if trades else 0

        # ── 9. Enhanced metrics ────────────────────────────────────────
        analyzer = BacktestAnalyzer()

        # Raw daily returns for sharpe (decimal)
        raw_rets = [dr.return_pct / 100.0 for dr in daily_returns]
        sharpe = analyzer.sharpe_ratio(raw_rets)
        annualized_ret = (
            (total_pnl / initial_capital)
            * (252 / max(len(trading_dates), 1))
            * 100
            if initial_capital
            else 0
        )

        # Max drawdown details
        cum_returns = [(dr.trade_date, dr.cumulative_return_pct) for dr in daily_returns]
        max_dd, dd_duration, _, _ = analyzer.max_drawdown_details_from_cumulative(cum_returns)
        max_dd_pct = self._max_drawdown(daily_returns)

        # Information ratio (use 0 as benchmark if none provided)
        info_ratio = 0.0
        if sharpe != 0:
            info_ratio = analyzer.information_ratio(raw_rets, [0.0] * len(raw_rets))

        # Turnover rate
        turnover = analyzer.turnover_rate(trades, initial_capital)

        # Hit rate
        hit_rate = analyzer.hit_rate(attempted_buys, filled_buys) if attempted_buys else 0

        # ── 10. IC Analysis ────────────────────────────────────────────
        ic_summary = None
        if request.enable_ic_analysis and daily_scores:
            ic_summary = self._compute_ic_analysis(
                daily_scores, daily_close_prices, effective_holding_days
            )

        return BacktestResult(
            strategy_name=strategy.name,
            start_date=start_date,
            end_date=end_date,
            stock_pool=request.stock_pool,
            initial_capital=initial_capital,
            position_size=position_size,
            trade_count=len(trades),
            win_rate=win_rate,
            total_return_pct=round((total_pnl / initial_capital) * 100, 2)
            if initial_capital
            else 0,
            max_drawdown_pct=max_dd_pct,
            trades=trades,
            daily_returns=daily_returns,
            annualized_return=round(annualized_ret, 2),
            sharpe_ratio=round(sharpe, 4),
            information_ratio=round(info_ratio, 4),
            max_drawdown_duration=dd_duration,
            turnover_rate=round(turnover, 4),
            hit_rate=round(hit_rate, 4),
            ic_summary=ic_summary,
        )

    # ------------------------------------------------------------------
    # Legacy: _run_stock (unchanged)
    # ------------------------------------------------------------------

    def _run_stock(self, request: BacktestRequest, stock: BacktestStockBars) -> list[BacktestTrade]:
        strategy = self.registry.get(request.strategy_name)
        bars = sorted(stock.bars, key=lambda bar: bar.trade_date)
        trades: list[BacktestTrade] = []
        holding_days = max(request.holding_days, 1)

        for index, bar in enumerate(bars):
            entry_index = index + 1
            exit_index = entry_index + holding_days
            if exit_index >= len(bars):
                continue
            if bar.trade_date < request.start_date or bar.trade_date > request.end_date:
                continue

            history = bars[: index + 1]
            context = self._build_context(stock.context, request.strategy_params, bars, index)
            signal = strategy.evaluate(stock.code, history, context=context)
            if not signal.matched:
                continue

            entry_bar = bars[entry_index]
            exit_bar = bars[exit_index]
            noise_entry = 1 + abs(random.gauss(0, 0.001))
            noise_exit = 1 - abs(random.gauss(0, 0.001))
            entry_price = entry_bar.open * noise_entry
            exit_price = exit_bar.open * noise_exit

            quantity = request.position_size / entry_price if entry_price else 0
            pnl = (exit_price - entry_price) * quantity
            return_pct = ((exit_price - entry_price) / entry_price) * 100 if entry_price else 0
            trades.append(
                BacktestTrade(
                    stock_code=stock.code,
                    stock_name=stock.name,
                    strategy_name=strategy.name,
                    entry_date=entry_bar.trade_date,
                    exit_date=exit_bar.trade_date,
                    entry_price=round(entry_price, 4),
                    exit_price=round(exit_price, 4),
                    quantity=round(quantity, 4),
                    pnl=round(pnl, 2),
                    return_pct=round(return_pct, 2),
                    signal_score=signal.score,
                    signal_reason=signal.reason,
                    metrics=signal.metrics,
                )
            )

        return trades

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Enhanced helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_bar(
        bars_dict: dict[str, list[DailyBar]],
        code: str,
        dt: date,
    ) -> DailyBar | None:
        """Return the DailyBar for *code* on *dt*, or None."""
        bars = bars_dict.get(code, [])
        for bar in bars:
            if bar.trade_date == dt:
                return bar
        return None

    @staticmethod
    def _avg_volume(
        bars_dict: dict[str, list[DailyBar]],
        code: str,
        dt: date,
        window: int = 20,
    ) -> float:
        """Compute average volume over *window* bars ending before *dt*."""
        bars = bars_dict.get(code, [])
        vols: list[float] = []
        for bar in bars:
            if bar.trade_date < dt:
                v = bar.volume or 0
                if v > 0:
                    vols.append(float(v))
        if not vols:
            return 1.0  # avoid division by zero
        recent = vols[-window:]
        return sum(recent) / len(recent)

    def _compute_ic_analysis(
        self,
        daily_scores: dict[date, dict[str, float]],
        daily_close_prices: dict[date, dict[str, float]],
        n_forward: int,
    ) -> object:
        """Build IC analysis from daily model scores and forward returns.

        Forward return = close[t+N] / close[t] - 1, where N = n_forward.
        """
        analyze_dates = sorted(daily_scores.keys())
        if len(analyze_dates) < 2:
            return None

        all_codes = set()
        for scores in daily_scores.values():
            all_codes.update(scores.keys())
        all_codes = sorted(all_codes)

        # Build scores_df: index=date, columns=code, values=model_score
        scores_records: list[dict] = []
        for dt in analyze_dates:
            row: dict = {"date": pd.Timestamp(dt)}
            for code in all_codes:
                row[code] = daily_scores.get(dt, {}).get(code)
            scores_records.append(row)
        scores_df = pd.DataFrame(scores_records).set_index("date")

        # Build forward returns: return from dt close to dt+N close
        n_forward = n_forward or 5
        ret_records: list[dict] = []
        for i, dt in enumerate(analyze_dates):
            row: dict = {"date": pd.Timestamp(dt)}
            future_idx = min(i + n_forward, len(analyze_dates) - 1)
            future_dt = analyze_dates[future_idx]
            for code in all_codes:
                close_today = daily_close_prices.get(dt, {}).get(code)
                close_future = daily_close_prices.get(future_dt, {}).get(code)
                if (
                    close_today is not None
                    and close_future is not None
                    and close_today > 0
                ):
                    row[code] = (close_future / close_today) - 1.0
                else:
                    row[code] = None
            ret_records.append(row)
        ret_df = pd.DataFrame(ret_records).set_index("date")

        analyzer = BacktestAnalyzer()
        return analyzer.ic_analysis(scores_df, ret_df)
