"""
TabNet trainer: attentive tabular deep learning via pytorch-tabnet (optional).

Implements BaseModel interface.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

try:
    from pytorch_tabnet.tab_model import TabNetRegressor

    _TABNET_AVAILABLE = True
except ImportError:  # pragma: no cover
    TabNetRegressor = None  # type: ignore[assignment]
    _TABNET_AVAILABLE = False
    logger.info("pytorch-tabnet not installed; TabNetTrainer will be unavailable.")


class TabNetTrainer(BaseModel):
    """TabNet model trainer (uses pytorch-tabnet)."""

    def __init__(self):
        if not _TABNET_AVAILABLE:
            raise RuntimeError(
                "pytorch-tabnet is required. Install with: pip install pytorch-tabnet"
            )

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> Any:
        n_d = getattr(config, "num_leaves", 64)
        n_a = n_d
        n_steps = max(3, n_d // 16)

        model = TabNetRegressor(
            n_d=n_d,
            n_a=n_a,
            n_steps=n_steps,
            gamma=getattr(config, "learning_rate", 1.3),
            n_independent=2,
            n_shared=2,
            seed=getattr(config, "seed", 42),
        )

        model.fit(
            X_train=X_train,
            y_train=y_train.reshape(-1, 1),
            eval_set=[(X_valid, y_valid.reshape(-1, 1))],
            eval_name=["valid"],
            eval_metric=["rmse"],
            max_epochs=getattr(config, "n_estimators", 200),
            patience=getattr(config, "early_stopping_rounds", 20),
            batch_size=1024,
            virtual_batch_size=256,
            num_workers=0,
            drop_last=False,
        )

        return model

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        return model.predict(X).ravel()

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        try:
            imp = model.feature_importances_
            return dict(
                sorted(zip(feature_names, imp), key=lambda kv: -kv[1])
            )
        except Exception:
            return {}

    def save(self, model: Any, path: str) -> None:
        model.save_model(path)

    def load(self, path: str) -> Any:
        if not _TABNET_AVAILABLE:
            raise RuntimeError("pytorch-tabnet is not installed.")
        return TabNetRegressor()
