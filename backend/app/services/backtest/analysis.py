"""
BacktestAnalyzer: post-backtest performance analysis.

Provides calculation of:
- Sharpe ratio (annualized)
- Information ratio
- Maximum drawdown with detailed timing and duration
- Turnover rate
- Win rate by period (monthly / weekly)
- IC analysis (Pearson IC and Rank IC time series)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date

import numpy as np
import pandas as pd

from app.schemas.backtest import BacktestTrade
from app.schemas.factor import ICAnalysisSummary, ICPoint

TRADING_DAYS_PER_YEAR = 252


class BacktestAnalyzer:
    """Collection of static analysis methods for backtest results."""

    # ------------------------------------------------------------------
    # Risk / return metrics
    # ------------------------------------------------------------------

    @staticmethod
    def sharpe_ratio(daily_returns: list[float]) -> float:
        """Annualised Sharpe ratio.

        Sharpe = mean(daily_ret) / std(daily_ret) * sqrt(252)

        Returns 0.0 if the returns list is empty or std is 0.
        """
        if not daily_returns:
            return 0.0
        rets = np.array(daily_returns, dtype=np.float64)
        std = rets.std(ddof=1)
        if std == 0:
            return 0.0
        return float(rets.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))

    @staticmethod
    def information_ratio(
        returns: list[float],
        bench_returns: list[float],
    ) -> float:
        """Information ratio: mean(excess_return) / std(excess_return) * sqrt(252).

        Excess return = portfolio return - benchmark return (both as raw decimal
        returns, e.g. 0.01 = 1%).

        Returns 0.0 if excess return std is 0 or lengths mismatch.
        """
        n = len(returns)
        if n == 0 or len(bench_returns) != n:
            return 0.0
        rets = np.array(returns, dtype=np.float64)
        bench = np.array(bench_returns, dtype=np.float64)
        excess = rets - bench
        std = excess.std(ddof=1)
        if std == 0:
            return 0.0
        return float(excess.mean() / std * math.sqrt(TRADING_DAYS_PER_YEAR))

    @staticmethod
    def max_drawdown_details(
        daily_returns: list[float],
    ) -> tuple[float, int, date | None, date | None]:
        """Compute maximum drawdown with timing details.

        Parameters
        ----------
        daily_returns : list[float]
            Sequence of daily *percentage* returns (e.g. [0.5, -0.3, ...]).
            These are treated as point-in-time observations; the method
            computes a cumulative equity curve from them.
            Alternatively, pass cumulative values directly by calling
            ``max_drawdown_details_from_cumulative``.

        Returns
        -------
        tuple[float, int, date | None, date | None]
            (max_drawdown_pct, duration_days, start, recovery)

        Notes
        -----
        This overload accepts simple P&L values.  If you have per-date
        cumulative return percentages, use ``_from_cumulative`` instead
        for correct peak-to-trough measurement.
        """
        if not daily_returns:
            return 0.0, 0, None, None
        rets = np.array(daily_returns, dtype=np.float64)
        cumulative = np.cumsum(rets)  # additive returns

        peak = np.maximum.accumulate(cumulative)
        drawdown = peak - cumulative
        if len(drawdown) == 0:
            return 0.0, 0, None, None

        max_dd_idx = int(np.argmax(drawdown))
        max_dd_val = float(drawdown[max_dd_idx])

        # Find the start (last time we were at the peak before max_dd)
        peak_val = peak[max_dd_idx]
        # Look backwards for the first occurrence of this peak value
        start_idx = max_dd_idx
        for i in range(max_dd_idx, -1, -1):
            if cumulative[i] >= peak_val:
                start_idx = i
            else:
                break

        # Find recovery (first time cumulative exceeds peak after max_dd)
        recovery_idx = max_dd_idx
        for i in range(max_dd_idx + 1, len(cumulative)):
            if cumulative[i] >= peak_val:
                recovery_idx = i
                break

        duration_days = recovery_idx - start_idx

        return max_dd_val, duration_days, None, None  # dates need external mapping

    @staticmethod
    def max_drawdown_details_from_cumulative(
        cumulative_returns: list[tuple[date, float]],
    ) -> tuple[float, int, date | None, date | None]:
        """Compute max drawdown from cumulative equity curve with dates.

        Parameters
        ----------
        cumulative_returns : list[tuple[date, float]]
            Pairs of (date, cumulative_return_pct).

        Returns
        -------
        tuple[float, int, date | None, date | None]
            (max_drawdown_pct, duration_days, start_date, recovery_date)
        """
        if not cumulative_returns:
            return 0.0, 0, None, None

        dates = [d for d, _ in cumulative_returns]
        vals = np.array([v for _, v in cumulative_returns], dtype=np.float64)

        peak = np.maximum.accumulate(vals)
        drawdown = peak - vals
        if len(drawdown) == 0:
            return 0.0, 0, None, None

        max_dd_idx = int(np.argmax(drawdown))
        max_dd_val = float(drawdown[max_dd_idx])
        peak_val = peak[max_dd_idx]

        start_idx = max_dd_idx
        for i in range(max_dd_idx, -1, -1):
            if vals[i] >= peak_val:
                start_idx = i
            else:
                break

        recovery_idx = max_dd_idx
        for i in range(max_dd_idx + 1, len(vals)):
            if vals[i] >= peak_val:
                recovery_idx = i
                break

        start_date = dates[start_idx] if start_idx < len(dates) else None
        recovery_date = dates[recovery_idx] if recovery_idx < len(dates) else None
        # Duration in days
        if start_date is not None and recovery_date is not None:
            duration_days = (recovery_date - start_date).days
        else:
            duration_days = recovery_idx - start_idx

        return max_dd_val, duration_days, start_date, recovery_date

    # ------------------------------------------------------------------
    # Trading activity metrics
    # ------------------------------------------------------------------

    @staticmethod
    def turnover_rate(
        trades: list[BacktestTrade],
        capital: float,
    ) -> float:
        """Annualised turnover rate.

        turnover = sum(trade_value_per_year) / (2 * capital)

        Uses the total buy+notional value over the period, annualised
        based on the number of trading days spanned by the trades.

        Returns 0.0 if there are no trades or capital is 0.
        """
        if not trades or capital <= 0:
            return 0.0

        total_notional = sum(
            trade.entry_price * trade.quantity for trade in trades
        )

        # Estimate trading days spanned
        all_dates = set()
        for t in trades:
            all_dates.add(t.entry_date)
            all_dates.add(t.exit_date)
        if not all_dates:
            return 0.0
        days_span = (max(all_dates) - min(all_dates)).days or 1
        years = days_span / 365.0

        return float(total_notional / capital / years)

    @staticmethod
    def win_rate_by_period(
        trades: list[BacktestTrade],
        freq: str = "M",
    ) -> pd.DataFrame:
        """Compute win rate grouped by period (monthly 'M' or weekly 'W').

        Returns
        -------
        pd.DataFrame
            Columns: period, total_trades, winning_trades, win_rate
        """
        if not trades:
            return pd.DataFrame(
                columns=["period", "total_trades", "winning_trades", "win_rate"]
            )

        records = []
        for t in trades:
            # Use exit_date for period assignment
            period_key = t.exit_date
            records.append(
                {
                    "date": pd.Timestamp(period_key),
                    "is_win": 1 if t.pnl > 0 else 0,
                }
            )

        df = pd.DataFrame(records)
        if freq == "W":
            df["period"] = df["date"].dt.to_period("W")
        else:
            df["period"] = df["date"].dt.to_period("M")

        grouped = df.groupby("period").agg(
            total_trades=("is_win", "count"),
            winning_trades=("is_win", "sum"),
        )
        grouped["win_rate"] = grouped["winning_trades"] / grouped["total_trades"]
        grouped = grouped.reset_index()
        grouped["period"] = grouped["period"].astype(str)
        return grouped

    # ------------------------------------------------------------------
    # Hit rate (limit-up hit rate from exchange sim context)
    # ------------------------------------------------------------------

    @staticmethod
    def hit_rate(
        attempted_buys: int,
        filled_buys: int,
    ) -> float:
        """Fraction of buy attempts that were actually filled.

        (i.e. not rejected due to limit-up or suspension)

        Parameters
        ----------
        attempted_buys : int
            Total number of attempted buy signals.
        filled_buys : int
            Number of buy signals that successfully executed.
        """
        if attempted_buys <= 0:
            return 0.0
        return filled_buys / attempted_buys

    # ------------------------------------------------------------------
    # IC Analysis
    # ------------------------------------------------------------------

    @staticmethod
    def ic_analysis(
        scores_df: pd.DataFrame,
        forward_returns: pd.DataFrame,
    ) -> ICAnalysisSummary:
        """Compute IC (Information Coefficient) analysis across dates.

        Parameters
        ----------
        scores_df : pd.DataFrame
            Index = date, Columns = code, Values = model score.
        forward_returns : pd.DataFrame
            Index = date, Columns = code, Values = forward return.
            Must share the same index (dates) as scores_df.

        Returns
        -------
        ICAnalysisSummary
            Summary statistics plus per-date IC series.
        """
        # Align on common dates and codes
        common_dates = scores_df.index.intersection(forward_returns.index)
        if len(common_dates) == 0:
            return ICAnalysisSummary(
                ic_mean=0.0, ic_std=0.0, icir=0.0,
                rank_ic_mean=0.0, rank_ic_std=0.0, rank_icir=0.0,
                ic_series=[],
            )

        ic_points: list[ICPoint] = []
        pearson_ics: list[float] = []
        rank_ics: list[float] = []

        for dt in common_dates:
            scores_row = scores_df.loc[dt]
            ret_row = forward_returns.loc[dt]

            # Find codes present in both
            common_codes = scores_row.dropna().index.intersection(
                ret_row.dropna().index
            )
            if len(common_codes) < 3:
                # Too few observations for meaningful IC
                continue

            s = scores_row[common_codes].astype(float).values
            r = ret_row[common_codes].astype(float).values

            # Pearson IC
            pearson_ic = float(np.corrcoef(s, r)[0, 1]) if len(s) > 1 else 0.0
            if not np.isnan(pearson_ic):
                pearson_ics.append(pearson_ic)

            # Rank (Spearman) IC
            if len(s) > 1:
                from scipy.stats import spearmanr
                rank_ic = float(spearmanr(s, r)[0])
            else:
                rank_ic = 0.0
            if not np.isnan(rank_ic):
                rank_ics.append(rank_ic)

            # Marshal dt from potential pd.Timestamp
            dt_val = dt.date() if isinstance(dt, pd.Timestamp) else dt
            ic_points.append(
                ICPoint(
                    date=dt_val,
                    ic=round(pearson_ic, 6) if not np.isnan(pearson_ic) else 0.0,
                    rank_ic=round(rank_ic, 6) if not np.isnan(rank_ic) else 0.0,
                )
            )

        if pearson_ics:
            ic_mean = float(np.mean(pearson_ics))
            ic_std = float(np.std(pearson_ics, ddof=1))
            icir = ic_mean / ic_std * math.sqrt(TRADING_DAYS_PER_YEAR) if ic_std else 0.0
            rank_ic_mean = float(np.mean(rank_ics))
            rank_ic_std = float(np.std(rank_ics, ddof=1))
            rank_icir = (
                rank_ic_mean / rank_ic_std * math.sqrt(TRADING_DAYS_PER_YEAR)
                if rank_ic_std
                else 0.0
            )
        else:
            ic_mean = ic_std = icir = 0.0
            rank_ic_mean = rank_ic_std = rank_icir = 0.0

        return ICAnalysisSummary(
            ic_mean=round(ic_mean, 6),
            ic_std=round(ic_std, 6),
            icir=round(icir, 6),
            rank_ic_mean=round(rank_ic_mean, 6),
            rank_ic_std=round(rank_ic_std, 6),
            rank_icir=round(rank_icir, 6),
            ic_series=ic_points,
        )
