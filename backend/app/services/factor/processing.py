"""
Factor post-processing utilities.

Standard pipeline: fill_na -> winsorize -> standardize -> neutralize
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fill_na(df: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill then zero-fill remaining NaN values.

    Operates column-wise within each column independently.
    """
    out = df.ffill().fillna(0.0)
    return out


def winsorize(
    df: pd.DataFrame,
    limits: tuple[float, float] = (0.01, 0.01),
) -> pd.DataFrame:
    """Clip extreme values at the given quantile *limits* (lower, upper).

    Parameters
    ----------
    limits : (lower, upper)
        Fraction of values to clip on each tail. Default ``(0.01, 0.01)``
        clips the bottom 1% and top 1%.

    Returns
    -------
    pd.DataFrame
        Winsorized copy.
    """
    out = df.copy()
    lower = out.quantile(limits[0])
    upper = out.quantile(1.0 - limits[1])
    for col in out.columns:
        out[col] = out[col].clip(lower=lower[col], upper=upper[col])
    return out


def standardize(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score standardization per date (row).

    For each row (date), subtract the cross-sectional mean and divide by
    the cross-sectional standard deviation.  NaN-safe.
    """
    row_mean = df.mean(axis=1)
    row_std = df.std(axis=1, ddof=1)
    # Avoid division by zero
    row_std = row_std.replace(0.0, np.nan)
    out = df.sub(row_mean, axis=0).div(row_std, axis=0)
    return out


def neutralize(df: pd.DataFrame, by: pd.Series) -> pd.DataFrame:
    """Remove the effect of a grouping variable *by*.

    For each factor column, subtract the group-mean so that the
    within-group mean becomes zero.  This is a simple form of
    industry or market-cap neutralization.

    Parameters
    ----------
    by : pd.Series
        A Series with the same index as *df*, containing group labels
        (e.g. industry codes, market-cap buckets).
    """
    out = df.copy()
    for col in out.columns:
        group_mean = out[col].groupby(by).transform("mean")
        out[col] = out[col] - group_mean
    return out


def process(
    df: pd.DataFrame,
    std: bool = True,
    win_limits: tuple[float, float] | None = None,
    neu_by: pd.Series | None = None,
) -> pd.DataFrame:
    """Convenience pipeline: fill_na → (winsorize) → (standardize) → (neutralize).

    Parameters
    ----------
    df : pd.DataFrame
        Raw factor values (index = dates, columns = factors/assets).
    std : bool
        Whether to apply cross-sectional standardization.
    win_limits : (lower, upper) | None
        If provided, winsorize at these quantiles before standardization.
    neu_by : pd.Series | None
        If provided, neutralize factors by removing group means.
    """
    out = fill_na(df)
    if win_limits is not None:
        out = winsorize(out, win_limits)
    if std:
        out = standardize(out)
    if neu_by is not None:
        out = neutralize(out, neu_by)
    return out
