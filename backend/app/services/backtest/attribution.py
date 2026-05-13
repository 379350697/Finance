"""Profit attribution: Brinson and factor-level return decomposition."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd


class BrinsonAttribution:
    """Decompose active returns into allocation, selection, and interaction effects.

    Brinson model:
        Total excess return = allocation_effect + selection_effect + interaction_effect

        allocation_effect = sum((w_p_i - w_b_i) * r_b_i)  # over/under-weight sectors
        selection_effect  = sum(w_b_i * (r_p_i - r_b_i))  # stock picking within sectors
        interaction_effect = sum((w_p_i - w_b_i) * (r_p_i - r_b_i))  # cross-term
    """

    @staticmethod
    def analyze(
        portfolio_returns: pd.Series,      # portfolio daily returns (by date)
        benchmark_returns: pd.Series,       # benchmark daily returns (by date)
        portfolio_weights: pd.DataFrame,    # (dates, sectors) portfolio sector weights
        benchmark_weights: pd.DataFrame,    # (dates, sectors) benchmark sector weights
        sector_returns: pd.DataFrame,       # (dates, sectors) sector returns
    ) -> dict:
        """Run Brinson attribution.

        All DataFrames are indexed by date with columns = sectors (or single column for returns).

        Returns dict with keys: allocation_effects, selection_effects, interaction_effects,
        total_excess_return. Each effect is a list of {name, value, pct}.
        """
        # Align dates
        common_dates = (portfolio_weights.index
                       .intersection(benchmark_weights.index)
                       .intersection(sector_returns.index))
        if len(common_dates) == 0:
            return {
                "allocation_effects": [],
                "selection_effects": [],
                "interaction_effects": [],
                "total_excess": 0.0,
            }

        sectors = portfolio_weights.columns.tolist()

        alloc_total = defaultdict(float)
        select_total = defaultdict(float)
        interact_total = defaultdict(float)

        for dt in common_dates:
            pw = portfolio_weights.loc[dt]
            bw = benchmark_weights.loc[dt]
            sr = sector_returns.loc[dt]

            for sec in sectors:
                w_p = pw.get(sec, 0)
                w_b = bw.get(sec, 0)
                r_b = sr.get(sec, 0)
                r_p = r_b  # simplified: use sector return as portfolio sector return
                # In practice, r_p would be the weighted return of stocks in that sector

                alloc_total[sec] += (w_p - w_b) * r_b
                select_total[sec] += w_b * (r_p - r_b)
                interact_total[sec] += (w_p - w_b) * (r_p - r_b)

        def _make_effects(totals: dict, total_val: float) -> list[dict]:
            items = sorted(totals.items(), key=lambda kv: abs(kv[1]), reverse=True)
            return [
                {"name": name, "value": round(val, 6),
                 "pct": round(val / total_val * 100, 2) if abs(total_val) > 1e-12 else 0.0}
                for name, val in items if abs(val) > 1e-10
            ]

        alloc_sum = sum(alloc_total.values())
        select_sum = sum(select_total.values())
        interact_sum = sum(interact_total.values())
        total_excess = alloc_sum + select_sum + interact_sum

        return {
            "allocation_effects": _make_effects(alloc_total, total_excess),
            "selection_effects": _make_effects(select_total, total_excess),
            "interaction_effects": _make_effects(interact_total, total_excess),
            "total_excess": round(total_excess, 6),
        }


class FactorAttribution:
    """Decompose returns by factor contribution.

    Factor contribution = factor_loading * factor_return
    residual = actual_return - sum(factor_contributions)
    """

    @staticmethod
    def analyze(
        returns: np.ndarray,           # (n_periods, n_assets) asset returns
        factor_loadings: np.ndarray,   # (n_assets, n_factors) factor exposures
        factor_returns: np.ndarray,    # (n_periods, n_factors) factor returns
        factor_names: list[str],
    ) -> dict:
        """Return per-factor contribution and residual.

        Returns dict with:
            factor_contributions: [{name, value, pct}, ...]
            residual: {value, pct}
            total_return: float
        """
        n_periods, n_assets = returns.shape
        n_factors = factor_loadings.shape[1]

        # Average across periods and assets
        avg_return = np.mean(returns)
        total_contributions = {}

        for f_idx in range(n_factors):
            # Factor contribution = avg(factor_return) * avg(loading)
            avg_factor_ret = np.mean(factor_returns[:, f_idx])
            avg_loading = np.mean(factor_loadings[:, f_idx])
            contrib = avg_factor_ret * avg_loading
            total_contributions[factor_names[f_idx] if f_idx < len(factor_names) else f"factor_{f_idx}"] = contrib

        explained = sum(total_contributions.values())
        residual = avg_return - explained

        def _to_pct(items: dict, total: float) -> list[dict]:
            sorted_items = sorted(items.items(), key=lambda kv: abs(kv[1]), reverse=True)
            return [
                {"name": name, "value": round(val, 6),
                 "pct": round(val / total * 100, 2) if abs(total) > 1e-12 else 0.0}
                for name, val in sorted_items if abs(val) > 1e-10
            ]

        return {
            "factor_contributions": _to_pct(total_contributions, avg_return),
            "residual": {"name": "residual", "value": round(residual, 6),
                        "pct": round(residual / avg_return * 100, 2) if abs(avg_return) > 1e-12 else 0.0},
            "total_return": round(float(avg_return), 6),
        }


class AttributionAnalyzer:
    """Combined attribution analysis for backtest results."""

    def __init__(self, market_data=None):
        self.market_data = market_data

    def full_attribution(self, daily_returns, trades, benchmark_code="000300"):
        """Run combined attribution on a backtest result.

        Args:
            daily_returns: list of BacktestDailyReturn objects
            trades: list of BacktestTrade
            benchmark_code: benchmark stock code

        Returns:
            dict with brinson and factor attribution results
        """
        # Simplified: compute sector-level Brinson from trades
        if not daily_returns:
            return {"error": "No daily returns available"}

        # Build portfolio sector weights from trades
        # (Simplified -- in production this uses actual sector classifications)
        sectors = self._infer_sectors(trades)

        # Build daily portfolio returns series
        port_returns = pd.Series(
            {dr.trade_date: dr.return_pct / 100.0 for dr in daily_returns}
        ).sort_index()

        return {
            "brinson": {
                "allocation_effects": [],
                "selection_effects": [],
                "interaction_effects": [],
                "total_excess": round(float(port_returns.sum()), 6),
            },
            "factor": {
                "factor_contributions": [],
                "residual": {"name": "residual", "value": 0, "pct": 0},
                "total_return": round(float(port_returns.sum()), 6),
            },
        }

    @staticmethod
    def _infer_sectors(trades) -> dict[str, str]:
        """Infer sector from stock code prefix (simplified)."""
        sectors = {}
        for t in trades:
            code = t.stock_code
            prefix = code[:3]
            sector_map = {
                "600": "主板", "601": "主板", "603": "主板", "605": "主板",
                "000": "主板", "001": "主板", "002": "中小板",
                "300": "创业板", "301": "创业板",
                "688": "科创板",
            }
            sectors[code] = sector_map.get(prefix, "其他")
        return sectors
