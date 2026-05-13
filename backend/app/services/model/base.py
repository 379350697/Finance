"""Base model interface for multi-model training."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class BaseModel(ABC):
    """Abstract base for all model trainers."""

    @abstractmethod
    def fit(self, X_train: np.ndarray, y_train: np.ndarray,
            X_valid: np.ndarray, y_valid: np.ndarray, config: Any) -> Any:
        """Train model, return fitted model object."""
        ...

    @abstractmethod
    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        """Return 1D predictions array."""
        ...

    @abstractmethod
    def get_feature_importance(self, model: Any, feature_names: list[str]) -> dict[str, float]:
        """Return {feature_name: importance_score}."""
        ...

    @abstractmethod
    def save(self, model: Any, path: str) -> None:
        ...

    @abstractmethod
    def load(self, path: str) -> Any:
        ...
