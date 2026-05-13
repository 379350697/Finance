"""
ModelPredictor: inference on trained models (LightGBM, XGBoost, CatBoost, MLP).

Supports single-date prediction and batch prediction over a date range
(used for backtesting).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.core.config import settings

logger = logging.getLogger(__name__)

# Graceful imports
try:
    import lightgbm as lgb

    _LGB_AVAILABLE = True
except ImportError:  # pragma: no cover
    lgb = None  # type: ignore[assignment]
    _LGB_AVAILABLE = False


class ModelPredictor:
    """Loads a trained model and runs inference on factor data.

    Supports multiple model backends: lightgbm, xgboost, catboost, mlp.
    """

    def __init__(
        self,
        factor_engine: Any = None,
        columnar: Any = None,
    ) -> None:
        self._factor_engine = factor_engine
        self._columnar = columnar

    # ── properties (lazy init) ─────────────────────────────────────────

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

    def predict(
        self,
        model_name: str,
        codes: list[str],
        predict_date: date,
        factor_set: str = "alpha158",
        model_type: str = "lightgbm",
    ) -> pd.DataFrame:
        """Predict scores for a single date.

        Parameters
        ----------
        model_name : str
            Name of the trained model (used to locate the persisted file).
        codes : list[str]
            Stock codes to predict on.
        predict_date : date
            The target prediction date.
        factor_set : str
            Factor set name matching the one used during training.
        model_type : str
            Model backend: lightgbm, xgboost, catboost, or mlp.

        Returns
        -------
        pd.DataFrame
            Columns: ``code``, ``score``, ``rank``.
            Sorted by ``rank`` ascending (1 = highest score).
        """
        result = self.predict_batch(
            model_name=model_name,
            codes=codes,
            start_date=predict_date,
            end_date=predict_date,
            factor_set=factor_set,
            model_type=model_type,
        )
        # Return without the ``date`` column for single-date convenience.
        return result.drop(columns=["date"])

    def predict_batch(
        self,
        model_name: str,
        codes: list[str],
        start_date: date,
        end_date: date,
        factor_set: str = "alpha158",
        model_type: str = "lightgbm",
    ) -> pd.DataFrame:
        """Predict scores for a range of dates (for backtesting).

        Parameters
        ----------
        model_name : str
            Name of the trained model.
        codes : list[str]
            Stock codes to predict on.
        start_date : date
            First prediction date (inclusive).
        end_date : date
            Last prediction date (inclusive).
        factor_set : str
            Factor set name.
        model_type : str
            Model backend: lightgbm, xgboost, catboost, or mlp.

        Returns
        -------
        pd.DataFrame
            Columns: ``code``, ``date``, ``score``, ``rank``.
            Sorted by ``date`` ascending, then ``rank`` ascending within each date.
        """
        logger.info(
            "Predicting with model '%s' (type=%s) on %d codes from %s to %s (factor_set=%s)",
            model_name,
            model_type,
            len(codes),
            start_date,
            end_date,
            factor_set,
        )

        # 1. Load model
        model = self._load_model(model_name, model_type)

        # 2. Load factor data for the prediction window
        load_start = start_date - timedelta(days=60)
        factor_matrix = self.factor_engine.get_factor_matrix(
            codes=codes,
            start=load_start,
            end=end_date,
            factor_set=factor_set,
        )
        factor_names = self.factor_engine.factor_names(factor_set)
        n_dates, n_codes, n_factors = factor_matrix.shape

        if n_dates == 0 or n_codes == 0:
            logger.warning("No factor data available for prediction window.")
            return pd.DataFrame(columns=["code", "date", "score", "rank"])

        # Determine which rows correspond to actual prediction dates.
        all_dates = self.columnar.dates
        pred_dates = [d for d in all_dates if start_date <= d <= end_date]

        if not pred_dates:
            logger.warning(
                "No trading dates in prediction range [%s, %s].",
                start_date,
                end_date,
            )
            return pd.DataFrame(columns=["code", "date", "score", "rank"])

        factor_date_count = n_dates
        if factor_date_count < len(pred_dates):
            logger.warning(
                "Factor matrix has fewer dates (%d) than prediction range (%d). "
                "Truncating prediction range.",
                factor_date_count,
                len(pred_dates),
            )
            pred_dates = pred_dates[-factor_date_count:]

        # Take the rows corresponding to prediction dates (last N rows).
        pred_rows = factor_matrix[-len(pred_dates) :, :, :]

        # 3. Run inference per date
        rows: list[dict[str, Any]] = []
        for di, dt in enumerate(pred_dates):
            X = pred_rows[di, :, :]

            # Drop codes that have any NaN factor
            valid_mask = ~np.isnan(X).any(axis=1)
            valid_indices = np.where(valid_mask)[0]

            if len(valid_indices) == 0:
                continue

            X_valid = X[valid_indices, :]

            # Cross-sectional standardization
            mean = np.nanmean(X_valid, axis=0, keepdims=True)
            std = np.nanstd(X_valid, axis=0, ddof=1, keepdims=True)
            std[std == 0] = 1.0
            X_std = (X_valid - mean) / std

            # Predict using the appropriate backend
            scores = self._predict_inner(model, X_std, model_type)

            # Rank: highest score = rank 1
            order = np.argsort(-scores)
            ranks = np.empty(len(scores), dtype=int)
            ranks[order] = np.arange(1, len(scores) + 1)

            for idx, ci in enumerate(valid_indices):
                rows.append(
                    {
                        "code": codes[ci],
                        "date": dt,
                        "score": float(scores[idx]),
                        "rank": int(ranks[idx]),
                    }
                )

        result = pd.DataFrame(rows, columns=["code", "date", "score", "rank"])
        result = result.sort_values(["date", "rank"]).reset_index(drop=True)

        logger.info(
            "Prediction complete: %d rows across %d dates",
            len(result),
            len(pred_dates),
        )
        return result

    # ── internal ───────────────────────────────────────────────────────

    def _predict_inner(
        self, model: Any, X: np.ndarray, model_type: str
    ) -> np.ndarray:
        """Dispatch prediction to the correct backend.

        LightGBM requires ``num_iteration``; XGBoost requires wrapping in
        DMatrix; CatBoost/MLP use a plain ``.predict()`` call.
        """
        if model_type == "lightgbm":
            return model.predict(X, num_iteration=model.best_iteration)
        elif model_type == "xgboost":
            import xgboost as xgb

            dmat = xgb.DMatrix(X)
            return model.predict(dmat)
        elif model_type == "catboost":
            return model.predict(X).astype(np.float64)
        elif model_type == "mlp":
            return model.predict(X).astype(np.float64)
        else:
            raise ValueError(f"Unknown model_type: {model_type!r}")

    def _load_model(self, model_name: str, model_type: str = "lightgbm") -> Any:
        """Load a persisted model of the given type.

        The file extension is mapped from model_type:
        lightgbm -> .txt, xgboost -> .json, catboost -> .cbm, mlp -> .joblib
        """
        ext_map = {"lightgbm": ".txt", "xgboost": ".json", "catboost": ".cbm", "mlp": ".joblib"}
        ext = ext_map.get(model_type, ".txt")
        path = Path(settings.model_dir) / f"{model_name}{ext}"
        if not path.exists():
            raise FileNotFoundError(
                f"Model file not found: {path}. "
                f"Available: {self._list_available_models()}"
            )
        logger.info("Loading model from %s (type=%s)", path, model_type)

        if model_type == "lightgbm":
            if not _LGB_AVAILABLE:
                raise RuntimeError("lightgbm is not installed.")
            return lgb.Booster(model_file=str(path))
        elif model_type == "xgboost":
            import xgboost as xgb

            model = xgb.Booster()
            model.load_model(str(path))
            return model
        elif model_type == "catboost":
            from catboost import CatBoostRegressor

            return CatBoostRegressor().load_model(str(path))
        elif model_type == "mlp":
            import joblib

            return joblib.load(str(path))
        else:
            raise ValueError(f"Unknown model_type: {model_type!r}")

    def _list_available_models(self) -> list[str]:
        model_dir = Path(settings.model_dir)
        if not model_dir.exists():
            return []
        extensions = ["*.txt", "*.json", "*.cbm", "*.joblib"]
        stems: set[str] = set()
        for pattern in extensions:
            for p in model_dir.glob(pattern):
                stems.add(p.stem)
        return sorted(stems)
