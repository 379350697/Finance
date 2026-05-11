"""
ModelTrainer: Qlib-style LightGBM training with IC evaluation.

Pipeline:
    1. Load factor matrix via FactorEngine
    2. Build forward-return labels from close prices
    3. Time-series split (train / valid / test, no leakage)
    4. Standardize features
    5. Train LightGBM with early stopping
    6. Compute IC / Rank IC on test set
    7. Persist model and feature importance
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful import of optional dependencies
# ---------------------------------------------------------------------------

try:
    import lightgbm as lgb

    _LGB_AVAILABLE = True
except ImportError:  # pragma: no cover
    lgb = None  # type: ignore[assignment]
    _LGB_AVAILABLE = False
    logger.warning("lightgbm not installed; ModelTrainer will raise at runtime.")

try:
    from scipy.stats import pearsonr, spearmanr

    _SCIPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    pearsonr = None  # type: ignore[assignment]
    spearmanr = None  # type: ignore[assignment]
    _SCIPY_AVAILABLE = False
    logger.warning("scipy not installed; IC computation will fail.")

try:
    from sklearn.metrics import mean_absolute_error, mean_squared_error
except ImportError:  # pragma: no cover
    mean_squared_error = None  # type: ignore[assignment]
    mean_absolute_error = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Config & result models
# ---------------------------------------------------------------------------


class ModelConfig(BaseModel):
    """Configuration for a single model training run."""

    model_name: str  # e.g. "lgb_alpha158_v1"
    model_type: str = "lightgbm"
    factor_set: str = "alpha158"
    train_start: date
    train_end: date
    valid_start: date
    valid_end: date
    test_start: date
    test_end: date
    stock_pool: list[str] = []
    label_type: str = "next_ret5"  # next_ret1 / next_ret5 / next_ret10 / next_ret20

    # LightGBM hyper-parameters
    num_leaves: int = 32
    learning_rate: float = 0.05
    n_estimators: int = 200
    min_child_samples: int = 100
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    early_stopping_rounds: int = 20
    seed: int = 42
    n_jobs: int = -1
    verbosity: int = -1


class ModelTrainResult(BaseModel):
    """Result returned after a successful training run."""

    model_name: str
    model_type: str
    factor_set: str
    ic_mean: float
    ic_std: float
    icir: float
    rank_ic_mean: float
    rank_ic_std: float
    rank_icir: float
    mse: float
    mae: float
    feature_importance: dict[str, float]
    model_path: str

    class Config:
        arbitrary_types_allowed = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_label_horizon(label_type: str) -> int:
    """Extract the forward-return horizon from a label_type string.

    >>> _parse_label_horizon("next_ret5")
    5
    >>> _parse_label_horizon("next_ret20")
    20
    """
    if not label_type.startswith("next_ret"):
        raise ValueError(f"Unsupported label_type: {label_type}")
    return int(label_type.split("ret")[-1])


# ---------------------------------------------------------------------------
# ModelTrainer
# ---------------------------------------------------------------------------


class ModelTrainer:
    """Trains LightGBM models on factor data with Qlib-style evaluation."""

    def __init__(
        self,
        factor_engine: Any = None,
        columnar: Any = None,
    ) -> None:
        self._factor_engine = factor_engine
        self._columnar = columnar

    # ── properties ─────────────────────────────────────────────────────

    @property
    def factor_engine(self) -> Any:
        if self._factor_engine is None:
            try:
                from app.services.factor.engine import FactorEngine

                self._factor_engine = FactorEngine()
            except ImportError:
                raise RuntimeError(
                    "FactorEngine not available and no instance provided."
                )
        return self._factor_engine

    @property
    def columnar(self) -> Any:
        if self._columnar is None:
            try:
                from app.services.data.columnar import ColumnarDataStore

                self._columnar = ColumnarDataStore(store_path=settings.columnar_dir)
            except ImportError:
                raise RuntimeError(
                    "ColumnarDataStore not available and no instance provided."
                )
        return self._columnar

    # ── public API ─────────────────────────────────────────────────────

    def train(self, config: ModelConfig) -> ModelTrainResult:
        """Full training pipeline.

        Returns a ``ModelTrainResult`` with IC metrics, error metrics, and
        feature importance.
        """
        if not _LGB_AVAILABLE:
            raise RuntimeError(
                "lightgbm is required for training.  Install with: pip install lightgbm"
            )
        if not _SCIPY_AVAILABLE:
            raise RuntimeError(
                "scipy is required for IC computation.  Install with: pip install scipy"
            )

        logger.info("Starting training for model '%s'", config.model_name)

        # 1. Load data
        X, y, sample_dates, factor_names = self._build_dataset(config)

        # 2. Time-series split
        train_mask = np.array([d < config.valid_start for d in sample_dates])
        valid_mask = np.array(
            [config.valid_start <= d < config.test_start for d in sample_dates]
        )
        test_mask = np.array([d >= config.test_start for d in sample_dates])

        X_train = X[train_mask]
        y_train = y[train_mask]
        X_valid = X[valid_mask]
        y_valid = y[valid_mask]
        X_test = X[test_mask]
        y_test = y[test_mask]
        test_dates = sample_dates[test_mask]

        if len(X_train) == 0:
            raise ValueError(
                "No training samples after split. Check your date ranges."
            )
        if len(X_test) == 0:
            raise ValueError("No test samples after split. Check your date ranges.")

        logger.info(
            "Split: train=%d, valid=%d, test=%d samples",
            len(X_train),
            len(X_valid),
            len(X_test),
        )

        # 3. Standardize (fit on train, transform valid/test)
        X_train, X_valid, X_test = self._standardize(X_train, X_valid, X_test)

        # 4. Train LightGBM
        model = self.train_lightgbm(X_train, y_train, X_valid, y_valid, config)

        # 5. Predict on test set
        y_pred = model.predict(X_test, num_iteration=model.best_iteration)

        # 6. Compute metrics
        ic_mean, ic_std, icir = self._compute_ic(y_pred, y_test, test_dates)
        rank_ic_mean, rank_ic_std, rank_icir = self._compute_rank_ic(
            y_pred, y_test, test_dates
        )

        mse = float(np.mean((y_pred - y_test) ** 2))
        mae = float(np.mean(np.abs(y_pred - y_test)))

        # 7. Feature importance
        feat_imp = dict(
            sorted(
                zip(factor_names, model.feature_importance(importance_type="gain")),
                key=lambda kv: kv[1],
                reverse=True,
            )
        )

        # 8. Save model
        model_path = self.save_model(model, config.model_name)

        result = ModelTrainResult(
            model_name=config.model_name,
            model_type=config.model_type,
            factor_set=config.factor_set,
            ic_mean=ic_mean,
            ic_std=ic_std,
            icir=icir,
            rank_ic_mean=rank_ic_mean,
            rank_ic_std=rank_ic_std,
            rank_icir=rank_icir,
            mse=mse,
            mae=mae,
            feature_importance=feat_imp,
            model_path=str(model_path),
        )

        logger.info(
            "Training complete: IC=%.4f, ICIR=%.4f, RankIC=%.4f, RankICIR=%.4f",
            ic_mean,
            icir,
            rank_ic_mean,
            rank_icir,
        )
        return result

    # ── dataset construction ───────────────────────────────────────────

    def _build_dataset(
        self, config: ModelConfig
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
        """Build the full training dataset.

        Returns
        -------
        X : np.ndarray  (n_samples, n_factors)
            Factor values.
        y : np.ndarray  (n_samples,)
            Forward-return labels.
        sample_dates : np.ndarray  (n_samples,)
            Date of each sample (for time-series split).
        factor_names : list[str]
            Ordered factor names.
        """
        codes = config.stock_pool

        # 1. Factor matrix from FactorEngine
        factor_matrix = self.factor_engine.get_factor_matrix(
            codes=codes,
            start=config.train_start,
            end=config.test_end,
            factor_set=config.factor_set,
        )
        n_dates_f, n_codes_f, n_factors = factor_matrix.shape

        if n_dates_f == 0 or n_codes_f == 0 or n_factors == 0:
            raise ValueError(
                "Factor matrix is empty. Check stock_pool and date range."
            )

        factor_names = self.factor_engine.factor_names(config.factor_set)

        # 2. Close prices from columnar store
        close_panel = self.columnar.get_field(
            "close",
            start=config.train_start,
            end=config.test_end,
            codes=codes,
        )
        n_dates_c, n_codes_c = close_panel.shape

        # 3. Canonical date list
        all_columnar_dates = self.columnar.dates
        dates = [
            d
            for d in all_columnar_dates
            if config.train_start <= d <= config.test_end
        ]

        # Align factor matrix and close panel on date dimension.
        if n_dates_f != n_dates_c:
            logger.warning(
                "Date mismatch: factors=%d dates, close=%d dates. "
                "Truncating to the shorter length. Factor dates may not "
                "align perfectly with close dates.",
                n_dates_f,
                n_dates_c,
            )
            n_dates = min(n_dates_f, n_dates_c)
            factor_matrix = factor_matrix[:n_dates, :, :]
            close_panel = close_panel[:n_dates, :]
            if len(dates) > n_dates:
                dates = dates[:n_dates]
        else:
            n_dates = n_dates_f

        # Align on the code dimension too (both should match stock_pool order).
        n_codes = min(n_codes_f, n_codes_c)
        if n_codes_f != n_codes_c:
            logger.warning(
                "Code count mismatch: factors=%d, close=%d. Truncating.",
                n_codes_f,
                n_codes_c,
            )

        # 4. Build labels from close prices
        labels = self._build_labels(dates[:n_dates], codes[:n_codes], close_panel, config.label_type)

        # 5. Flatten: (n_dates, n_codes, n_factors) -> (n_dates * n_codes, n_factors)
        X = factor_matrix[:, :n_codes, :].reshape(-1, n_factors)
        y = labels.reshape(-1)

        # Create per-sample date array for splitting
        sample_dates = np.array(
            [dates[i] for i in range(n_dates) for _ in range(n_codes)]
        )

        # 6. Drop samples with NaN in features or labels
        nan_mask = np.isnan(X).any(axis=1) | np.isnan(y)
        X = X[~nan_mask]
        y = y[~nan_mask]
        sample_dates = sample_dates[~nan_mask]

        logger.info(
            "Dataset built: %d samples, %d factors, %d codes, %d dates",
            X.shape[0],
            n_factors,
            n_codes,
            n_dates,
        )
        return X, y, sample_dates, factor_names

    def _build_labels(
        self,
        dates: list[date],
        codes: list[str],
        close_panel: np.ndarray,
        label_type: str,
    ) -> np.ndarray:
        """Build forward-return labels from a close-price panel.

        Parameters
        ----------
        dates : list[date]
            Dates corresponding to axis 0 of *close_panel*.
        codes : list[str]
            Codes corresponding to axis 1 of *close_panel*.
        close_panel : np.ndarray
            Shape ``(n_dates, n_codes)``.
        label_type : str
            e.g. ``"next_ret5"`` for 5-day forward return.

        Returns
        -------
        np.ndarray
            Shape ``(n_dates, n_codes)``.  Rows near the end are NaN
            because the forward window extends beyond available data.
        """
        n = _parse_label_horizon(label_type)
        n_dates, n_codes = close_panel.shape

        labels = np.full((n_dates, n_codes), np.nan, dtype=np.float64)

        # forward_return[t] = close[t+n] / close[t] - 1
        for i in range(n_dates - n):
            labels[i, :] = close_panel[i + n, :] / close_panel[i, :] - 1.0

        return labels

    # ── standardization ────────────────────────────────────────────────

    @staticmethod
    def _standardize(
        X_train: np.ndarray,
        X_valid: np.ndarray | None,
        X_test: np.ndarray | None,
    ) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
        """Cross-sectionally z-score each factor column.

        Mean and std are computed on the training set and applied to all
        splits to avoid data leakage.
        """
        mean = np.nanmean(X_train, axis=0, keepdims=True)
        std = np.nanstd(X_train, axis=0, ddof=1, keepdims=True)
        std[std == 0] = 1.0  # avoid division by zero

        X_train = (X_train - mean) / std

        if X_valid is not None and len(X_valid) > 0:
            X_valid = (X_valid - mean) / std
        if X_test is not None and len(X_test) > 0:
            X_test = (X_test - mean) / std

        return X_train, X_valid, X_test

    # ── IC computation ─────────────────────────────────────────────────

    def _compute_ic(
        self,
        scores: np.ndarray,
        labels: np.ndarray,
        sample_dates: np.ndarray,
    ) -> tuple[float, float, float]:
        """Cross-sectional Pearson IC per date, then mean/std/ICIR.

        Parameters
        ----------
        scores : (n_samples,)
            Predicted scores.
        labels : (n_samples,)
            Actual forward returns.
        sample_dates : (n_samples,)
            Date of each sample.  IC is computed per unique date.

        Returns
        -------
        ic_mean : float
            Mean of per-date ICs.
        ic_std : float
            Standard deviation of per-date ICs.
        icir : float
            Information Coefficient / Information Ratio = ic_mean / ic_std.
        """
        daily_ics: list[float] = []
        unique_dates = sorted(set(sample_dates))

        for d in unique_dates:
            mask = sample_dates == d
            s = scores[mask]
            l = labels[mask]
            # Need at least 3 samples for meaningful correlation
            if len(s) < 3:
                continue
            # Remove any remaining NaN
            valid = ~(np.isnan(s) | np.isnan(l))
            if valid.sum() < 3:
                continue
            r, _ = pearsonr(s[valid], l[valid])
            if not np.isnan(r):
                daily_ics.append(r)

        if not daily_ics:
            return 0.0, 0.0, 0.0

        ic_mean = float(np.mean(daily_ics))
        ic_std = float(np.std(daily_ics, ddof=1))
        icir = ic_mean / ic_std if ic_std > 0 else 0.0

        return ic_mean, ic_std, icir

    def _compute_rank_ic(
        self,
        scores: np.ndarray,
        labels: np.ndarray,
        sample_dates: np.ndarray,
    ) -> tuple[float, float, float]:
        """Cross-sectional Spearman (Rank) IC per date, then mean/std/ICIR."""
        daily_ics: list[float] = []
        unique_dates = sorted(set(sample_dates))

        for d in unique_dates:
            mask = sample_dates == d
            s = scores[mask]
            l = labels[mask]
            if len(s) < 3:
                continue
            valid = ~(np.isnan(s) | np.isnan(l))
            if valid.sum() < 3:
                continue
            r, _ = spearmanr(s[valid], l[valid])
            if not np.isnan(r):
                daily_ics.append(r)

        if not daily_ics:
            return 0.0, 0.0, 0.0

        ic_mean = float(np.mean(daily_ics))
        ic_std = float(np.std(daily_ics, ddof=1))
        icir = ic_mean / ic_std if ic_std > 0 else 0.0

        return ic_mean, ic_std, icir

    # ── LightGBM training ──────────────────────────────────────────────

    def train_lightgbm(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: ModelConfig,
    ) -> Any:  # lgb.Booster
        """Train a LightGBM regressor with early stopping on the validation set.

        Returns a ``lgb.Booster`` with the best iteration selected.
        """
        params = {
            "objective": "regression",
            "metric": "rmse",
            "num_leaves": config.num_leaves,
            "learning_rate": config.learning_rate,
            "n_estimators": config.n_estimators,
            "min_child_samples": config.min_child_samples,
            "subsample": config.subsample,
            "colsample_bytree": config.colsample_bytree,
            "reg_alpha": config.reg_alpha,
            "reg_lambda": config.reg_lambda,
            "seed": config.seed,
            "n_jobs": config.n_jobs,
            "verbosity": config.verbosity,
            "force_col_wise": True,  # safer for wide datasets
        }

        train_data = lgb.Dataset(X_train, label=y_train)
        valid_data = lgb.Dataset(X_valid, label=y_valid, reference=train_data)

        model = lgb.train(
            params,
            train_data,
            valid_sets=[valid_data],
            num_boost_round=config.n_estimators,
            callbacks=[lgb.early_stopping(config.early_stopping_rounds)],
        )

        return model

    # ── persistence ────────────────────────────────────────────────────

    def save_model(
        self,
        model: Any,  # lgb.Booster
        model_name: str,
    ) -> Path:
        """Persist a LightGBM model to ``{model_dir}/{model_name}.txt``.

        Returns the resolved path to the saved file.
        """
        model_dir = Path(settings.model_dir)
        model_dir.mkdir(parents=True, exist_ok=True)
        path = model_dir / f"{model_name}.txt"
        model.save_model(str(path))
        logger.info("Model saved to %s", path)
        return path

    def load_model(self, model_name: str) -> Any:  # lgb.Booster
        """Load a persisted LightGBM model from ``{model_dir}/{model_name}.txt``."""
        if not _LGB_AVAILABLE:
            raise RuntimeError("lightgbm is not installed.")
        path = Path(settings.model_dir) / f"{model_name}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")
        return lgb.Booster(model_file=str(path))

    def list_trained_models(self) -> list[str]:
        """List model names for which persisted files exist."""
        model_dir = Path(settings.model_dir)
        if not model_dir.exists():
            return []
        return sorted(p.stem for p in model_dir.glob("*.txt"))
