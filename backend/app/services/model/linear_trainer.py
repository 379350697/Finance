"""
Linear trainer: Ridge/Lasso regression wrapper with cross-validation.

Implements BaseModel interface. Uses sklearn.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

try:
    from sklearn.linear_model import Ridge, RidgeCV, Lasso, LassoCV

    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    Ridge = None  # type: ignore[assignment]
    Lasso = None  # type: ignore[assignment]
    _SKLEARN_AVAILABLE = False
    logger.info("sklearn not installed; LinearTrainer will be unavailable.")


class LinearTrainer(BaseModel):
    """Linear model trainer (Ridge by default, Lasso optional).

    Parameters
    ----------
    model_type : str
        "ridge" or "lasso".
    """

    def __init__(self, model_type: str = "ridge"):
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError(
                "scikit-learn is required. Install with: pip install scikit-learn"
            )
        self.model_type = model_type

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> Any:
        alpha = getattr(config, "reg_alpha", 1.0)

        if self.model_type == "ridge":
            model = Ridge(alpha=alpha, random_state=getattr(config, "seed", 42))
        else:
            model = Lasso(
                alpha=alpha,
                max_iter=2000,
                random_state=getattr(config, "seed", 42),
            )

        model.fit(X_train, y_train)
        return model

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        return model.predict(X)

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        coef = model.coef_
        if coef.ndim > 1:
            coef = coef.ravel()
        return dict(
            sorted(
                zip(feature_names, np.abs(coef)),
                key=lambda kv: -kv[1],
            )
        )

    def save(self, model: Any, path: str) -> None:
        import joblib
        joblib.dump(model, path)

    def load(self, path: str) -> Any:
        import joblib
        return joblib.load(path)
