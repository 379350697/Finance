"""
ParamSpace: hyperparameter search space definitions for model tuning.

Provides preset search spaces for common model types:
    - lightgbm, xgboost, catboost, mlp, lstm
"""

from __future__ import annotations

from typing import Any

# Type alias for a search space: dict mapping param_name to a dict with
# "type" ("int", "float", "categorical") and bounds/choices.
SearchSpace = dict[str, dict[str, Any]]


class ParamSpace:
    """Predefined hyperparameter search spaces for model tuning.

    Usage::

        space = ParamSpace.lightgbm()
        # -> {"num_leaves": {"type": "int", "low": 16, "high": 256, "log": True}, ...}
    """

    @staticmethod
    def lightgbm() -> SearchSpace:
        return {
            "num_leaves": {"type": "int", "low": 16, "high": 256, "log": True},
            "learning_rate": {"type": "float", "low": 0.01, "high": 0.3, "log": True},
            "n_estimators": {"type": "int", "low": 50, "high": 500},
            "min_child_samples": {"type": "int", "low": 20, "high": 500, "log": True},
            "subsample": {"type": "float", "low": 0.5, "high": 1.0},
            "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
            "reg_alpha": {"type": "float", "low": 1e-8, "high": 10.0, "log": True},
            "reg_lambda": {"type": "float", "low": 1e-8, "high": 10.0, "log": True},
        }

    @staticmethod
    def xgboost() -> SearchSpace:
        return {
            "max_depth": {"type": "int", "low": 3, "high": 12},
            "learning_rate": {"type": "float", "low": 0.01, "high": 0.3, "log": True},
            "n_estimators": {"type": "int", "low": 50, "high": 500},
            "subsample": {"type": "float", "low": 0.5, "high": 1.0},
            "colsample_bytree": {"type": "float", "low": 0.5, "high": 1.0},
            "reg_alpha": {"type": "float", "low": 1e-8, "high": 10.0, "log": True},
            "reg_lambda": {"type": "float", "low": 1e-8, "high": 10.0, "log": True},
        }

    @staticmethod
    def catboost() -> SearchSpace:
        return {
            "depth": {"type": "int", "low": 4, "high": 10},
            "learning_rate": {"type": "float", "low": 0.01, "high": 0.3, "log": True},
            "iterations": {"type": "int", "low": 50, "high": 500},
            "l2_leaf_reg": {"type": "float", "low": 1e-8, "high": 10.0, "log": True},
        }

    @staticmethod
    def mlp() -> SearchSpace:
        return {
            "hidden_layers": {"type": "categorical", "choices": [1, 2, 3]},
            "hidden_units": {"type": "categorical", "choices": [64, 128, 256, 512]},
            "dropout": {"type": "float", "low": 0.0, "high": 0.5},
            "learning_rate": {"type": "float", "low": 1e-4, "high": 1e-2, "log": True},
            "batch_size": {"type": "categorical", "choices": [64, 128, 256]},
        }

    @staticmethod
    def lstm() -> SearchSpace:
        return {
            "hidden_size": {"type": "categorical", "choices": [64, 128, 256]},
            "num_layers": {"type": "int", "low": 1, "high": 3},
            "dropout": {"type": "float", "low": 0.0, "high": 0.5},
            "learning_rate": {"type": "float", "low": 1e-4, "high": 1e-2, "log": True},
            "batch_size": {"type": "categorical", "choices": [64, 128, 256]},
        }

    @classmethod
    def get(cls, model_type: str) -> SearchSpace:
        """Return the search space for a given model type."""
        method = getattr(cls, model_type, None)
        if method is None:
            raise ValueError(
                f"No ParamSpace defined for {model_type!r}. "
                f"Available: lightgbm, xgboost, catboost, mlp, lstm"
            )
        return method()
