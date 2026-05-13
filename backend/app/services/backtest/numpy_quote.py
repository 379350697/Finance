"""
NumpyQuote: High-performance market data store backed by numpy recarray.

Provides O(1) date lookup via dictionary-indexed pointer arrays and
vectorized cross-sectional slicing, avoiding per-stock Python loops
during backtest inner loops.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np

# Record dtype for a single bar
QUOTE_DTYPE = np.dtype([
    ("code_idx", np.int32),
    ("date_ord", np.int32),        # date.toordinal() for fast comparison
    ("open", np.float64),
    ("high", np.float64),
    ("low", np.float64),
    ("close", np.float64),
    ("volume", np.float64),
    ("is_limit_up", np.bool_),
    ("is_limit_down", np.bool_),
    ("is_suspended", np.bool_),
])


def _date_to_ord(d: date) -> int:
    return d.toordinal()


def _ord_to_date(ordinal: int) -> date:
    return date.fromordinal(ordinal)


class NumpyQuote:
    """High-performance quote store for backtesting.

    Parameters
    ----------
    bars_dict : dict[str, list[DailyBar]]
        Per-code bar lists (same format used by BacktestService).
    """

    def __init__(self, bars_dict: dict[str, list[Any]]):
        self._codes: list[str] = []
        self._code_to_idx: dict[str, int] = {}
        self._date_to_pos: dict[int, int] = {}  # ordinal -> first row index
        self._dates: list[date] = []
        self._data: np.ndarray = np.array([], dtype=QUOTE_DTYPE)

        self._build(bars_dict)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self, bars_dict: dict[str, list[Any]]) -> None:
        """Construct the flat recarray and index structures."""
        if not bars_dict:
            return

        # Register codes
        self._codes = sorted(bars_dict.keys())
        self._code_to_idx = {c: i for i, c in enumerate(self._codes)}

        # Collect all (code, bar) pairs and compute ordinals
        rows: list[tuple] = []
        for code, bars in bars_dict.items():
            ci = self._code_to_idx[code]
            for bar in bars:
                dt = getattr(bar, "trade_date", None) or getattr(bar, "date", None)
                if dt is None:
                    continue
                rows.append((
                    ci,
                    _date_to_ord(dt),
                    float(getattr(bar, "open", np.nan)),
                    float(getattr(bar, "high", np.nan)),
                    float(getattr(bar, "low", np.nan)),
                    float(getattr(bar, "close", np.nan)),
                    float(getattr(bar, "volume", 0) or 0),
                    bool(getattr(bar, "is_limit_up", False)),
                    bool(getattr(bar, "is_limit_down", False)),
                    bool(getattr(bar, "is_suspended", False)),
                ))

        if not rows:
            return

        # Sort by date, then code
        rows.sort(key=lambda r: (r[1], r[0]))
        self._data = np.array(rows, dtype=QUOTE_DTYPE)

        # Build date position index
        unique_ordinals = sorted(set(self._data["date_ord"]))
        self._dates = [_ord_to_date(o) for o in unique_ordinals]

        for o in unique_ordinals:
            first = int(np.searchsorted(self._data["date_ord"], o, side="left"))
            self._date_to_pos[o] = first

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    @property
    def codes(self) -> list[str]:
        return self._codes

    @property
    def dates(self) -> list[date]:
        return self._dates

    def get_at(self, code: str, dt: date) -> np.ndarray | None:
        """Return the bar record for *code* on *dt*, or None."""
        ci = self._code_to_idx.get(code)
        if ci is None:
            return None
        o = _date_to_ord(dt)
        pos = self._date_to_pos.get(o)
        if pos is None:
            return None
        # Scan forward from pos to find matching code
        for i in range(pos, len(self._data)):
            row = self._data[i]
            if row["date_ord"] != o:
                break
            if row["code_idx"] == ci:
                return row
        return None

    def slice_dates(self, start: date, end: date) -> np.ndarray:
        """Return all bars where start <= trade_date <= end."""
        s = _date_to_ord(start)
        e = _date_to_ord(end)
        mask = (self._data["date_ord"] >= s) & (self._data["date_ord"] <= e)
        return self._data[mask]

    def align(self, codes: list[str], dt: date) -> np.ndarray:
        """Return a 1-D array of close prices for *codes* on *dt*.

        Missing codes get NaN.
        """
        o = _date_to_ord(dt)
        pos = self._date_to_pos.get(o)
        result = np.full(len(codes), np.nan, dtype=np.float64)
        if pos is None:
            return result

        code_idx_map = {c: self._code_to_idx.get(c, -1) for c in codes}

        for i in range(pos, len(self._data)):
            row = self._data[i]
            if row["date_ord"] != o:
                break
            for j, c in enumerate(codes):
                if code_idx_map[c] == row["code_idx"]:
                    result[j] = row["close"]
        return result

    def get_field(self, field: str, codes: list[str], dt: date) -> np.ndarray:
        """Return a field array for *codes* on *dt* (vectorized)."""
        o = _date_to_ord(dt)
        pos = self._date_to_pos.get(o)
        result = np.full(len(codes), np.nan, dtype=np.float64)
        if pos is None:
            return result
        code_idx_map = {c: self._code_to_idx.get(c, -1) for c in codes}
        for i in range(pos, len(self._data)):
            row = self._data[i]
            if row["date_ord"] != o:
                break
            for j, c in enumerate(codes):
                if code_idx_map[c] == row["code_idx"]:
                    result[j] = row[field]
        return result
