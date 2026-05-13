"""
DatasetH: Qlib-style dataset abstraction with train/valid/test segmentation.

DatasetH
    Single-segment dataset (one contiguous date range).
    ``prepare()`` returns (X, y, dates, factor_names).

TSDatasetH
    Time-series dataset that handles train/valid/test split via segment
    configs.  Each segment is a DatasetH.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TSDatasetH:
    """Three-segment time-series dataset.

    Parameters
    ----------
    train : DatasetH
    valid : DatasetH or None
    test : DatasetH
    """

    train: DatasetH
    valid: DatasetH | None
    test: DatasetH

    def prepare(
        self,
    ) -> tuple[
        tuple[np.ndarray, np.ndarray, np.ndarray, list[str]],
        tuple[np.ndarray, np.ndarray, np.ndarray, list[str]] | None,
        tuple[np.ndarray, np.ndarray, np.ndarray, list[str]],
    ]:
        """Prepare all three segments.

        Returns
        -------
        train_data : (X, y, dates, factor_names)
        valid_data : same tuple or None
        test_data  : same tuple
        """
        train_data = self.train.prepare()
        valid_data = self.valid.prepare() if self.valid is not None else None
        test_data = self.test.prepare()
        return train_data, valid_data, test_data


class DatasetH:
    """A single-segment dataset wrapping factor matrix and labels.

    Parameters
    ----------
    X : np.ndarray, shape (n_samples, n_factors)
    y : np.ndarray, shape (n_samples,)
    sample_dates : np.ndarray, shape (n_samples,)
    factor_names : list[str]
    name : str, optional
        Segment label for logging.
    """

    def __init__(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sample_dates: np.ndarray,
        factor_names: list[str],
        name: str = "",
    ):
        self.X = X
        self.y = y
        self.sample_dates = sample_dates
        self.factor_names = factor_names
        self.name = name

    def prepare(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
        """Return (X, y, dates, factor_names)."""
        return self.X, self.y, self.sample_dates, self.factor_names

    def __len__(self) -> int:
        return len(self.X)

    def __repr__(self) -> str:
        label = f" {self.name!r}" if self.name else ""
        return (
            f"DatasetH{label}(n_samples={len(self.X)}, "
            f"n_factors={len(self.factor_names)})"
        )

    # ------------------------------------------------------------------
    # slicing helpers
    # ------------------------------------------------------------------

    def subset(self, mask: np.ndarray, name: str = "") -> DatasetH:
        """Return a new DatasetH with rows where *mask* is True."""
        return DatasetH(
            X=self.X[mask],
            y=self.y[mask],
            sample_dates=self.sample_dates[mask],
            factor_names=self.factor_names,
            name=name or self.name,
        )

    def date_subset(
        self, start: date, end: date, name: str = ""
    ) -> DatasetH:
        """Return rows whose ``sample_dates`` fall in [start, end)."""
        mask = (self.sample_dates >= start) & (self.sample_dates < end)
        return self.subset(mask, name=name or f"{start}_{end}")
