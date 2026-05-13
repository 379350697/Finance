"""MLP / neural-network model trainer implementing the BaseModel interface."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

_IMPORT_ERROR_MSG = (
    "scikit-learn is required for MLP. Install with: pip install scikit-learn"
)

try:
    from sklearn.neural_network import MLPRegressor

    _MLP_AVAILABLE = True
except ImportError:  # pragma: no cover
    MLPRegressor = None  # type: ignore[assignment]
    _MLP_AVAILABLE = False

try:
    import joblib as _joblib

    _JOBLIB_AVAILABLE = True
except ImportError:  # pragma: no cover
    _joblib = None  # type: ignore[assignment]
    _JOBLIB_AVAILABLE = False


class MLPTrainer(BaseModel):
    """Trainer wrapping sklearn MLPRegressor for factor-model prediction.

    Note
    ----
    MLPRegressor does not support a separate validation set for early
    stopping natively.  We use ``early_stopping=True`` with
    ``validation_fraction=0.1`` and pass the union of train + valid
    for fitting.  The valid set provided by the caller is used only
    for this split internally; the actual validation is handled by
    scikit-learn.
    """

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> Any:
        if not _MLP_AVAILABLE:
            raise RuntimeError(_IMPORT_ERROR_MSG)

        # MLPRegressor uses early_stopping + validation_fraction internally,
        # so we combine training and validation data.
        X_combined = (
            np.vstack([X_train, X_valid]) if len(X_valid) > 0 else X_train
        )
        y_combined = (
            np.hstack([y_train, y_valid]) if len(y_valid) > 0 else y_train
        )

        params = {
            "hidden_layer_sizes": getattr(config, "hidden_layer_sizes", (128, 64, 32)),
            "activation": getattr(config, "activation", "relu"),
            "solver": getattr(config, "solver", "adam"),
            "alpha": getattr(config, "alpha", 0.0001),
            "learning_rate_init": getattr(config, "learning_rate", 0.001),
            "max_iter": getattr(config, "n_estimators", 200),
            "random_state": getattr(config, "seed", 42),
            "early_stopping": True,
            "validation_fraction": 0.1,
            "n_iter_no_change": getattr(config, "early_stopping_rounds", 10),
        }

        model = MLPRegressor(**params)
        model.fit(X_combined, y_combined)

        return model

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        return model.predict(X).astype(np.float64)

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        # MLPRegressor does not have a straightforward per-feature
        # importance measure.  Return an empty mapping.
        logger.debug("MLP does not provide native feature importance.")
        return {}

    def save(self, model: Any, path: str) -> None:
        if not _JOBLIB_AVAILABLE:
            raise RuntimeError(
                "joblib is required for saving MLP models. "
                "Install with: pip install joblib"
            )
        _joblib.dump(model, path)

    def load(self, path: str) -> Any:
        if not _JOBLIB_AVAILABLE:
            raise RuntimeError(
                "joblib is required for loading MLP models. "
                "Install with: pip install joblib"
            )
        return _joblib.load(path)
