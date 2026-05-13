"""XGBoost model trainer implementing the BaseModel interface."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

_IMPORT_ERROR_MSG = "xgboost is required. Install with: pip install xgboost"

try:
    import xgboost as xgb

    _XGB_AVAILABLE = True
except ImportError:  # pragma: no cover
    xgb = None  # type: ignore[assignment]
    _XGB_AVAILABLE = False


class XGBoostTrainer(BaseModel):
    """Trainer wrapping xgboost for factor-model prediction."""

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> Any:
        if not _XGB_AVAILABLE:
            raise RuntimeError(_IMPORT_ERROR_MSG)

        params = {
            "objective": "reg:squarederror",
            "eval_metric": "rmse",
            "max_depth": getattr(config, "max_depth", 6),
            "learning_rate": getattr(config, "learning_rate", 0.05),
            "n_estimators": getattr(config, "n_estimators", 200),
            "subsample": getattr(config, "subsample", 0.8),
            "colsample_bytree": getattr(config, "colsample_bytree", 0.8),
            "reg_alpha": getattr(config, "reg_alpha", 0.1),
            "reg_lambda": getattr(config, "reg_lambda", 0.1),
            "seed": getattr(config, "seed", 42),
            "nthread": getattr(config, "n_jobs", -1),
            "verbosity": getattr(config, "verbosity", 0),
        }

        dtrain = xgb.DMatrix(X_train, label=y_train)
        dvalid = xgb.DMatrix(X_valid, label=y_valid)

        evals = [(dtrain, "train"), (dvalid, "eval")]
        evals_result: dict = {}

        early_stopping_rounds = getattr(config, "early_stopping_rounds", 20)
        n_estimators = params.pop("n_estimators")

        model = xgb.train(
            params,
            dtrain,
            num_boost_round=n_estimators,
            evals=evals,
            evals_result=evals_result,
            early_stopping_rounds=early_stopping_rounds,
            verbose_eval=False,
        )

        return model

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        dmatrix = xgb.DMatrix(X)
        return model.predict(dmatrix)

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        scores = model.get_score(importance_type="gain")
        result: dict[str, float] = {}
        for i, name in enumerate(feature_names):
            key = f"f{i}"
            result[name] = float(scores.get(key, 0.0))
        return dict(
            sorted(result.items(), key=lambda kv: kv[1], reverse=True)
        )

    def save(self, model: Any, path: str) -> None:
        model.save_model(path)

    def load(self, path: str) -> Any:
        if not _XGB_AVAILABLE:
            raise RuntimeError(_IMPORT_ERROR_MSG)
        model = xgb.Booster()
        model.load_model(path)
        return model
