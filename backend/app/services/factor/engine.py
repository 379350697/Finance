"""
FactorEngine: orchestrates factor computation, caching, and retrieval.

Supports per-stock parquet caching and optional columnar (HDF5) storage.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.schemas.market import DailyBar
from app.services.factor.alpha158 import Alpha158
from app.services.factor.alpha360 import Alpha360
from app.services.factor.expression import FactorExpression, FactorSet

logger = logging.getLogger(__name__)

FACTOR_CACHE_DIR = Path("data/factors")

# Registry mapping factor-set name -> builder class
_BUILDERS: dict[str, type] = {
    "alpha158": Alpha158,
    "alpha360": Alpha360,
}


class FactorEngine:
    """Orchestrates factor computation with parquet and columnar backends."""

    def __init__(
        self,
        market_data: Any = None,
        columnar: Any | None = None,
    ):
        """*market_data* should expose ``get_daily_bars(code, start, end) -> list[DailyBar]``.
        *columnar* is an optional ``ColumnarDataStore`` instance.
        """
        self._market_data = market_data
        self._columnar = columnar
        self._expr_cache: Any = None  # ExpressionCache, lazy-init

    # ── helpers ────────────────────────────────────────────────────────

    @property
    def expr_cache(self) -> Any:
        if self._expr_cache is None:
            try:
                from app.services.data.expression_cache import ExpressionCache
                from app.core.config import settings

                self._expr_cache = ExpressionCache(
                    cache_dir=settings.expression_cache_dir,
                    ttl_days=settings.expression_cache_ttl_days,
                )
            except ImportError:
                self._expr_cache = None
        return self._expr_cache

    @staticmethod
    def _resolve_builder(factor_set: str):
        try:
            return _BUILDERS[factor_set]
        except KeyError:
            raise ValueError(
                f"Unknown factor_set '{factor_set}'. Available: {list(_BUILDERS)}"
            )

    @staticmethod
    def _cache_path(factor_set: str, code: str) -> Path:
        d = FACTOR_CACHE_DIR / factor_set
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{code}.parquet"

    def _bars_to_df(self, bars: list[DailyBar]) -> pd.DataFrame:
        """Convert a list of DailyBar to an OHLCV DataFrame indexed by trade_date."""
        if not bars:
            return pd.DataFrame()
        records = [
            {
                "open":   b.open,
                "high":   b.high,
                "low":    b.low,
                "close":  b.close,
                "volume": b.volume or 0.0,
            }
            for b in bars
        ]
        dates = [b.trade_date for b in bars]
        df = pd.DataFrame(records, index=pd.Index(dates, name="trade_date"))
        df = df.sort_index()
        return df

    def _load_cached(self, factor_set: str, code: str) -> pd.DataFrame | None:
        path = self._cache_path(factor_set, code)
        if not path.exists():
            return None
        df = pd.read_parquet(path)
        if "trade_date" in df.columns:
            df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
            df = df.set_index("trade_date")
        return df

    def _save_cache(self, factor_set: str, code: str, df: pd.DataFrame) -> None:
        path = self._cache_path(factor_set, code)
        out = df.reset_index()
        if "trade_date" not in out.columns:
            out = out.rename_axis("trade_date").reset_index()
        out.to_parquet(path)

    # ── factor name resolution ─────────────────────────────────────────

    def factor_names(self, factor_set: str = "alpha158") -> list[str]:
        """Return the ordered list of factor names for *factor_set*."""
        builder = self._resolve_builder(factor_set)
        return [expr.name for expr in builder.build_expressions()]

    # ── core computation ───────────────────────────────────────────────

    def compute_factors(
        self,
        codes: list[str],
        start: date,
        end: date,
        factor_set: str = "alpha158",
        use_expr_cache: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """Compute factors per-stock, caching each to parquet.

        Returns
        -------
        dict[str, pd.DataFrame]
            ``{code: DataFrame(index=trade_date, columns=factor_names)}``
        """
        builder = self._resolve_builder(factor_set)
        expressions = builder.build_expressions()
        factor_set_obj = FactorSet(expressions)
        cache = self.expr_cache if use_expr_cache else None

        result: dict[str, pd.DataFrame] = {}

        # Pre-check expression cache for full batch
        if cache is not None:
            all_hit = True
            for code in codes:
                cached_df = cache.get(f"{factor_set}:{code}", [code], start, end)
                if cached_df is not None and not cached_df.empty:
                    result[code] = cached_df
                else:
                    all_hit = False
            if all_hit and len(result) == len(codes):
                return result
            # Partial hit: remove from result so we recompute all to avoid inconsistency
            if not all_hit:
                result = {}

        for code in codes:
            logger.info("Computing %s factors for %s …", factor_set, code)

            bars = self._get_bars(code, start, end)
            if not bars:
                logger.warning("No data for %s in [%s, %s]", code, start, end)
                continue

            ohlcv = self._bars_to_df(bars)
            if ohlcv.empty:
                continue

            # Incremental update: try to reuse cached data
            existing = self._load_cached(factor_set, code)
            if existing is not None and not existing.empty:
                last_cached_date = existing.index.max()
                if isinstance(last_cached_date, (date, pd.Timestamp)):
                    if isinstance(last_cached_date, pd.Timestamp):
                        last_cached_date = last_cached_date.date()
                    # Only recompute tail if needed
                    min_req_date = last_cached_date - timedelta(days=120)
                    ohlcv_tail = ohlcv.loc[ohlcv.index >= min_req_date]
                    tail_factors = factor_set_obj.evaluate_all(ohlcv_tail)
                    # Merge: overwrite tail, keep earlier cached rows
                    merged = existing.combine_first(tail_factors)
                    # Prefer tail where it exists
                    common_idx = tail_factors.index.intersection(merged.index)
                    merged.loc[common_idx] = tail_factors.loc[common_idx]
                    merged = merged.sort_index()
                else:
                    merged = factor_set_obj.evaluate_all(ohlcv)
            else:
                merged = factor_set_obj.evaluate_all(ohlcv)

            # Clip to requested date range
            mask = (merged.index >= pd.Timestamp(start)) & (merged.index <= pd.Timestamp(end))
            merged = merged.loc[mask]

            self._save_cache(factor_set, code, merged)
            if cache is not None:
                try:
                    cache.set(f"{factor_set}:{code}", [code], start, end, merged)
                except Exception:
                    pass  # cache write failures are non-fatal
            result[code] = merged

        return result

    def compute_factors_columnar(
        self,
        codes: list[str],
        start: date,
        end: date,
        factor_set: str = "alpha158",
    ) -> np.ndarray:
        """Compute factors and store as a 3-D array ``(n_dates, n_codes, n_factors)``.

        Requires a ``ColumnarDataStore`` instance.
        Raises ``RuntimeError`` if the columnar store is unavailable.
        """
        if self._columnar is None:
            raise RuntimeError("ColumnarDataStore is not available")

        # First compute per-stock (populates parquet cache as side-effect)
        per_stock = self.compute_factors(codes, start, end, factor_set)
        if not per_stock:
            return np.empty((0, 0, 0))

        names = self.factor_names(factor_set)

        # Build aligned 3-D array
        all_dates: set[date] = set()
        for df in per_stock.values():
            all_dates.update(d for d in df.index if isinstance(d, (date, pd.Timestamp)))
        sorted_dates = sorted(all_dates)
        date_index = {d: i for i, d in enumerate(sorted_dates)}

        n_dates = len(sorted_dates)
        n_codes = len(codes)
        n_factors = len(names)
        arr = np.full((n_dates, n_codes, n_factors), np.nan, dtype=np.float64)

        for ci, code in enumerate(codes):
            df = per_stock.get(code)
            if df is None or df.empty:
                continue
            for di, d in enumerate(df.index):
                dt = d.date() if isinstance(d, pd.Timestamp) else d
                ri = date_index.get(dt)
                if ri is None:
                    continue
                row = df.iloc[di]
                for fi, fname in enumerate(names):
                    val = row.get(fname)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        arr[ri, ci, fi] = float(val)

        # Persist to columnar store
        self._columnar.save_factors(
            factor_set=factor_set,
            factor_names=names,
            array_3d=arr,
            dates=sorted_dates,
            codes=codes,
        )
        return arr

    def get_factor_matrix(
        self,
        codes: list[str],
        start: date,
        end: date,
        factor_set: str = "alpha158",
    ) -> np.ndarray:
        """Return a 3-D ``(n_dates, n_codes, n_factors)`` array.

        Prefers columnar store; falls back to building from parquet cache.
        """
        names = self.factor_names(factor_set)

        # Try columnar first.
        if self._columnar is not None:
            try:
                loaded_names, arr = self._columnar.load_factors(
                    factor_set=factor_set,
                    factor_names=names,
                    start=start,
                    end=end,
                    codes=codes,
                )
                return arr
            except Exception:
                logger.debug(
                    "Columnar load failed for %s, falling back to parquet.",
                    factor_set,
                    exc_info=True,
                )

        # Fallback: build from per-stock parquet cache.
        n_codes = len(codes)
        n_factors = len(names)

        all_dates: set[date] = set()
        code_dfs: dict[str, pd.DataFrame] = {}
        for code in codes:
            df = self._load_cached(factor_set, code)
            if df is not None and not df.empty:
                # Clip to range
                mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
                df = df.loc[mask]
                if not df.empty:
                    code_dfs[code] = df
                    all_dates.update(
                        d.date() if isinstance(d, pd.Timestamp) else d for d in df.index
                    )

        if not all_dates:
            return np.empty((0, n_codes, n_factors))

        sorted_dates = sorted(all_dates)
        date_index = {d: i for i, d in enumerate(sorted_dates)}

        n_d = len(sorted_dates)
        arr = np.full((n_d, n_codes, n_factors), np.nan, dtype=np.float64)

        for ci, code in enumerate(codes):
            df = code_dfs.get(code)
            if df is None:
                continue
            for di, d in enumerate(df.index):
                dt = d.date() if isinstance(d, pd.Timestamp) else d
                ri = date_index.get(dt)
                if ri is None:
                    continue
                row = df.iloc[di]
                for fi, fname in enumerate(names):
                    val = row.get(fname)
                    if val is not None and not (isinstance(val, float) and np.isnan(val)):
                        arr[ri, ci, fi] = float(val)

        return arr

    # ── internal ───────────────────────────────────────────────────────

    def _get_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        """Fetch daily bars, supporting both MarketDataService and callable providers."""
        if self._market_data is None:
            raise RuntimeError("No market data provider configured")
        return self._market_data.get_daily_bars(code, start, end)
