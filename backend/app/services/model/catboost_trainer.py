"""CatBoost model trainer implementing the BaseModel interface."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

_IMPORT_ERROR_MSG = "catboost is required. Install with: pip install catboost"

try:
    from catboost import CatBoostRegressor

    _CATBOOST_AVAILABLE = True
except ImportError:  # pragma: no cover
    CatBoostRegressor = None  # type: ignore[assignment]
    _CATBOOST_AVAILABLE = False


class CatBoostTrainer(BaseModel):
    """Trainer wrapping CatBoost for factor-model prediction."""

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> Any:
        if not _CATBOOST_AVAILABLE:
            raise RuntimeError(_IMPORT_ERROR_MSG)

        params = {
            "loss_function": "RMSE",
            "eval_metric": "RMSE",
            "depth": getattr(config, "depth", 6),
            "learning_rate": getattr(config, "learning_rate", 0.05),
            "iterations": getattr(config, "n_estimators", 200),
            "subsample": getattr(config, "subsample", 0.8),
            "l2_leaf_reg": getattr(config, "reg_lambda", 3.0),
            "random_seed": getattr(config, "seed", 42),
            "thread_count": getattr(config, "n_jobs", -1),
            "verbose": getattr(config, "verbosity", 0),
            "allow_writing_files": False,
        }

        early_stopping_rounds = getattr(config, "early_stopping_rounds", 20)
        params["early_stopping_rounds"] = early_stopping_rounds

        model = CatBoostRegressor(**params)
        model.fit(
            X_train,
            y_train,
            eval_set=(X_valid, y_valid),
            verbose=params.get("verbose", 0) > 0,
        )

        return model

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        return model.predict(X).astype(np.float64)

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        raw = model.get_feature_importance()
        result = {}
        for i, name in enumerate(feature_names):
            result[name] = float(raw[i]) if i < len(raw) else 0.0
        return dict(
            sorted(result.items(), key=lambda kv: kv[1], reverse=True)
        )

    def save(self, model: Any, path: str) -> None:
        model.save_model(path)

    def load(self, path: str) -> Any:
        if not _CATBOOST_AVAILABLE:
            raise RuntimeError(_IMPORT_ERROR_MSG)
        return CatBoostRegressor().load_model(path)
