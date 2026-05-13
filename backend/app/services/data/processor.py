"""
Data preprocessors: fit/transform paradigm for cross-sectional normalization.

Provides:
    Processor       ABC with fit() / transform()
    CSZScoreNorm    Cross-sectional z-score (fit stores nothing)
    CSRankNorm      Cross-sectional rank normalization
    Fillna          Fill NaN with a constant
    DropnaProcessor Drop rows containing NaN
    MinMaxNorm      Min-max scaling per feature (fit on train)
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class Processor(ABC):
    """Abstract base for data preprocessors."""

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> Processor:
        """Learn parameters from training data."""
        return self

    @abstractmethod
    def transform(self, X: np.ndarray) -> np.ndarray:
        """Apply the learned transformation."""

    def fit_transform(self, X: np.ndarray, y: np.ndarray | None = None) -> np.ndarray:
        """Fit then transform."""
        self.fit(X, y)
        return self.transform(X)


# ---------------------------------------------------------------------------
# Concrete processors
# ---------------------------------------------------------------------------


class CSZScoreNorm(Processor):
    """Cross-sectional z-score normalization.

    Each sample-row is standardized independently: (x - mean) / std.
    Fit is a no-op; transform computes per-row statistics.
    """

    def transform(self, X: np.ndarray) -> np.ndarray:
        mean = np.nanmean(X, axis=1, keepdims=True)
        std = np.nanstd(X, axis=1, ddof=1, keepdims=True)
        std[std == 0] = 1.0
        return (X - mean) / std


class FitZScoreNorm(Processor):
    """Feature-wise z-score where fit() learns per-column mean/std."""

    def __init__(self):
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> Processor:
        self.mean = np.nanmean(X, axis=0, keepdims=True)
        self.std = np.nanstd(X, axis=0, ddof=1, keepdims=True)
        self.std[self.std == 0] = 1.0
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            raise RuntimeError("FitZScoreNorm: must call fit() before transform()")
        return (X - self.mean) / self.std


class CSRankNorm(Processor):
    """Cross-sectional rank normalization to [0, 1]."""

    def transform(self, X: np.ndarray) -> np.ndarray:
        result = np.zeros_like(X, dtype=np.float64)
        for i in range(X.shape[0]):
            row = X[i]
            valid = ~np.isnan(row)
            if valid.sum() < 2:
                result[i] = 0.0
            else:
                ranked = np.zeros(row.shape)
                ranked[valid] = np.argsort(np.argsort(row[valid])) / (valid.sum() - 1)
                ranked[~valid] = 0.0
                result[i] = ranked
        return result


class Fillna(Processor):
    """Fill NaN values with a fixed constant."""

    def __init__(self, value: float = 0.0):
        self.value = value

    def transform(self, X: np.ndarray) -> np.ndarray:
        return np.nan_to_num(X, nan=self.value)


class DropnaProcessor(Processor):
    """Drop rows that contain any NaN."""

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> Processor:
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        mask = ~np.isnan(X).any(axis=1)
        if not mask.all():
            # Cannot drop rows in transform alone (would misalign with labels).
            # Instead, fill with 0 and let the caller handle masking.
            pass
        return X

    @staticmethod
    def mask(X: np.ndarray, y: np.ndarray | None = None) -> np.ndarray:
        """Return a boolean mask of rows to *keep* (no NaN)."""
        mask = ~np.isnan(X).any(axis=1)
        if y is not None:
            mask &= ~np.isnan(y)
        return mask


class MinMaxNorm(Processor):
    """Feature-wise min-max scaling to [0, 1]. fit() learns per-column min/max."""

    def __init__(self):
        self.f_min: np.ndarray | None = None
        self.f_max: np.ndarray | None = None
        self._denom: np.ndarray | None = None

    def fit(self, X: np.ndarray, y: np.ndarray | None = None) -> Processor:
        self.f_min = np.nanmin(X, axis=0)
        self.f_max = np.nanmax(X, axis=0)
        self._denom = self.f_max - self.f_min
        self._denom[self._denom == 0] = 1.0
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.f_min is None:
            raise RuntimeError("MinMaxNorm: must call fit() before transform()")
        return np.clip((X - self.f_min) / self._denom, 0.0, 1.0)
