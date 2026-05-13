"""
DataHandlerLP: Qlib-style data pipeline orchestrator.

Replaces the inline ``_build_dataset()`` logic in ModelTrainer with a
composable fit/transform processor pipeline.

Pipeline:
    1. Load factor matrix from FactorEngine
    2. Build forward-return labels from close prices
    3. Fit processors on training segment
    4. Transform all segments
    5. Return segmented DatasetH / TSDatasetH
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import numpy as np

from app.services.data.dataset import DatasetH, TSDatasetH
from app.services.data.processor import (
    CSZScoreNorm,
    DropnaProcessor,
    Fillna,
    FitZScoreNorm,
    Processor,
)

logger = logging.getLogger(__name__)

# Default processor pipeline
_DEFAULT_PROCESSORS: list[Processor] = [
    Fillna(0.0),
    FitZScoreNorm(),
]


class DataHandlerLP:
    """Full data pipeline: load, segment, process, return.

    Parameters
    ----------
    factor_engine : FactorEngine
        Used to load factor matrices and factor names.
    columnar : ColumnarDataStore
        Used to load close prices for label construction.
    processors : list[Processor], optional
        Fit/transform pipeline. Defaults to Fillna(0) + FitZScoreNorm.
    """

    def __init__(
        self,
        factor_engine: Any = None,
        columnar: Any = None,
        processors: list[Processor] | None = None,
    ):
        self._factor_engine = factor_engine
        self._columnar = columnar
        self._processors = processors or [p.__class__() for p in _DEFAULT_PROCESSORS]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_dataset(
        self,
        factor_set: str,
        codes: list[str],
        train_start: date,
        train_end: date,
        valid_start: date | None = None,
        valid_end: date | None = None,
        test_start: date | None = None,
        test_end: date | None = None,
        label_type: str = "next_ret5",
    ) -> TSDatasetH:
        """Build a full time-series dataset with train/valid/test segments.

        Returns a ``TSDatasetH`` whose ``prepare()`` yields the three segments.
        """
        factor_engine = self.factor_engine
        columnar = self.columnar

        if test_start is None:
            test_start = valid_end or train_end
        if test_end is None:
            test_end = train_end

        # Compute the full data range needed
        data_start = train_start
        data_end = max(test_end, valid_end or test_end)

        # 1. Load factor matrix
        factor_matrix = factor_engine.get_factor_matrix(
            codes=codes,
            start=data_start,
            end=data_end,
            factor_set=factor_set,
        )
        n_dates, n_codes, n_factors = factor_matrix.shape
        if n_dates == 0 or n_codes == 0 or n_factors == 0:
            raise ValueError("Factor matrix is empty.")

        factor_names = factor_engine.factor_names(factor_set)

        # 2. Load close prices
        close_panel = columnar.get_field(
            "close",
            start=data_start,
            end=data_end,
            codes=codes,
        )

        # 3. Resolve canonical dates
        all_columnar_dates = columnar.dates
        dates = [
            d
            for d in all_columnar_dates
            if data_start <= d <= data_end
        ]

        n_dates = min(n_dates, len(dates), close_panel.shape[0])
        factor_matrix = factor_matrix[:n_dates, :, :]
        close_panel = close_panel[:n_dates, :]
        dates = dates[:n_dates]
        n_codes = min(n_codes, close_panel.shape[1])

        # 4. Build labels
        labels = self._build_labels(dates, codes[:n_codes], close_panel, label_type)

        # 5. Flatten
        X = factor_matrix[:, :n_codes, :].reshape(-1, n_factors)
        y = labels.reshape(-1)
        sample_dates = np.array(
            [dates[i] for i in range(n_dates) for _ in range(n_codes)]
        )

        # 6. Drop NaN rows
        keep = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X, y, sample_dates = X[keep], y[keep], sample_dates[keep]

        logger.info(
            "DataHandlerLP: %d samples, %d factors, %d codes, %d dates",
            X.shape[0], n_factors, n_codes, n_dates,
        )

        # 7. Split into segments
        train_mask = np.array([d < train_end for d in sample_dates])

        valid_mask = np.zeros(len(sample_dates), dtype=bool)
        if valid_start is not None and valid_end is not None:
            valid_mask = np.array(
                [valid_start <= d < valid_end for d in sample_dates]
            )

        test_mask = np.array([d >= (test_start or valid_end or train_end) for d in sample_dates])

        # 8. Fit processors on training data, transform all
        X_train = X[train_mask]
        y_train = y[train_mask]
        X_valid = X[valid_mask] if valid_mask.any() else None
        X_test = X[test_mask]

        for proc in self._processors:
            proc.fit(X_train, y_train)

        X_train_proc = X_train.copy()
        for proc in self._processors:
            X_train_proc = proc.transform(X_train_proc)

        X_valid_proc: np.ndarray | None = None
        if X_valid is not None and len(X_valid) > 0:
            X_valid_proc = X_valid.copy()
            for proc in self._processors:
                X_valid_proc = proc.transform(X_valid_proc)

        X_test_proc = X_test.copy()
        for proc in self._processors:
            X_test_proc = proc.transform(X_test_proc)

        # 9. Assemble datasets
        train_ds = DatasetH(
            X=X_train_proc,
            y=y[train_mask],
            sample_dates=sample_dates[train_mask],
            factor_names=factor_names,
            name="train",
        )
        valid_ds: DatasetH | None = None
        if X_valid_proc is not None and len(X_valid_proc) > 0:
            valid_ds = DatasetH(
                X=X_valid_proc,
                y=y[valid_mask],
                sample_dates=sample_dates[valid_mask],
                factor_names=factor_names,
                name="valid",
            )
        test_ds = DatasetH(
            X=X_test_proc,
            y=y[test_mask],
            sample_dates=sample_dates[test_mask],
            factor_names=factor_names,
            name="test",
        )

        return TSDatasetH(train=train_ds, valid=valid_ds, test=test_ds)

    # ------------------------------------------------------------------
    # Properties (lazy)
    # ------------------------------------------------------------------

    @property
    def factor_engine(self) -> Any:
        if self._factor_engine is None:
            from app.services.factor.engine import FactorEngine
            self._factor_engine = FactorEngine()
        return self._factor_engine

    @property
    def columnar(self) -> Any:
        if self._columnar is None:
            from app.services.data.columnar import ColumnarDataStore
            from app.core.config import settings
            self._columnar = ColumnarDataStore(store_path=settings.columnar_dir)
        return self._columnar

    # ------------------------------------------------------------------
    # Label construction
    # ------------------------------------------------------------------

    def _build_labels(
        self,
        dates: list[date],
        codes: list[str],
        close_panel: np.ndarray,
        label_type: str,
    ) -> np.ndarray:
        """Build forward-return labels from close-price panel.

        Parameters
        ----------
        dates : list[date]
        codes : list[str]
        close_panel : np.ndarray, shape (n_dates, n_codes)
        label_type : str
            e.g. "next_ret5"

        Returns
        -------
        np.ndarray, shape (n_dates, n_codes)
        """
        n = _parse_label_horizon(label_type)
        n_dates, n_codes = close_panel.shape
        labels = np.full((n_dates, n_codes), np.nan, dtype=np.float64)
        for i in range(n_dates - n):
            labels[i, :] = close_panel[i + n, :] / close_panel[i, :] - 1.0
        return labels


def _parse_label_horizon(label_type: str) -> int:
    """Extract forward-return horizon from label_type string."""
    if not label_type.startswith("next_ret"):
        raise ValueError(f"Unsupported label_type: {label_type}")
    return int(label_type.split("ret")[-1])
