"""
Pure-Python fallback for Cython rolling window functions.

Same signatures as the Cython module — used when the .pyx file hasn't
been compiled.
"""

from __future__ import annotations

import numpy as np


def rolling_mean_1d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
) -> np.ndarray:
    """Rolling mean of a 1-D array (pure Python)."""
    n = len(x)
    mp = min_periods if min_periods > 0 else max(1, window // 2)
    out = np.full(n, np.nan, dtype=np.float64)

    for i in range(mp - 1, n):
        chunk = x[max(0, i - window + 1): i + 1]
        valid = chunk[~np.isnan(chunk)]
        if len(valid) >= mp:
            out[i] = np.mean(valid)
    return out


def rolling_std_1d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
    ddof: int = 1,
) -> np.ndarray:
    """Rolling std of a 1-D array (pure Python)."""
    n = len(x)
    mp = min_periods if min_periods > 0 else max(2, window // 2)
    out = np.full(n, np.nan, dtype=np.float64)

    for i in range(mp - 1, n):
        chunk = x[max(0, i - window + 1): i + 1]
        valid = chunk[~np.isnan(chunk)]
        if len(valid) > ddof and len(valid) >= mp:
            out[i] = np.std(valid, ddof=ddof)
    return out


def rolling_sum_1d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
) -> np.ndarray:
    """Rolling sum of a 1-D array (pure Python)."""
    n = len(x)
    mp = min_periods if min_periods > 0 else max(1, window // 2)
    out = np.full(n, np.nan, dtype=np.float64)

    for i in range(mp - 1, n):
        chunk = x[max(0, i - window + 1): i + 1]
        valid = chunk[~np.isnan(chunk)]
        if len(valid) >= mp:
            out[i] = np.sum(valid)
    return out


def rolling_mean_2d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
) -> np.ndarray:
    """Rolling mean along axis=0 for a 2-D array (pure Python)."""
    n, p = x.shape
    mp = min_periods if min_periods > 0 else max(1, window // 2)
    out = np.full((n, p), np.nan, dtype=np.float64)

    for k in range(p):
        for i in range(mp - 1, n):
            chunk = x[max(0, i - window + 1): i + 1, k]
            valid = chunk[~np.isnan(chunk)]
            if len(valid) >= mp:
                out[i, k] = np.mean(valid)
    return out


def rolling_std_2d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
    ddof: int = 1,
) -> np.ndarray:
    """Rolling std along axis=0 for a 2-D array (pure Python)."""
    n, p = x.shape
    mp = min_periods if min_periods > 0 else max(2, window // 2)
    out = np.full((n, p), np.nan, dtype=np.float64)

    for k in range(p):
        for i in range(mp - 1, n):
            chunk = x[max(0, i - window + 1): i + 1, k]
            valid = chunk[~np.isnan(chunk)]
            if len(valid) > ddof and len(valid) >= mp:
                out[i, k] = np.std(valid, ddof=ddof)
    return out


def rolling_sum_2d(
    x: np.ndarray,
    window: int,
    min_periods: int = -1,
) -> np.ndarray:
    """Rolling sum along axis=0 for a 2-D array (pure Python)."""
    n, p = x.shape
    mp = min_periods if min_periods > 0 else max(1, window // 2)
    out = np.full((n, p), np.nan, dtype=np.float64)

    for k in range(p):
        for i in range(mp - 1, n):
            chunk = x[max(0, i - window + 1): i + 1, k]
            valid = chunk[~np.isnan(chunk)]
            if len(valid) >= mp:
                out[i, k] = np.sum(valid)
    return out
