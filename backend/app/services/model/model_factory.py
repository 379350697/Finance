"""
ModelFactory: unified registry for creating model trainers by type string.

Replaces inline ``_get_trainer()`` dispatch with a central registry.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ModelFactory:
    """Central registry for model trainer creation.

    Usage::

        trainer = ModelFactory.create("lstm")
        model = trainer.fit(X_train, y_train, X_valid, y_valid, config)
    """

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, trainer_cls: type) -> None:
        """Register a trainer class under *name*."""
        cls._registry[name] = trainer_cls

    @classmethod
    def create(cls, model_type: str) -> Any:
        """Create a trainer instance for *model_type*.

        Returns a ``BaseModel`` instance.
        """
        # Populate registry on first use (lazy to avoid import-time failures)
        if not cls._registry:
            cls._populate()

        if model_type not in cls._registry:
            raise ValueError(
                f"Unknown model_type: {model_type!r}. "
                f"Available: {sorted(cls._registry)}"
            )

        trainer_cls = cls._registry[model_type]
        return trainer_cls()

    @classmethod
    def _populate(cls) -> None:
        """Populate the registry with all known trainers."""
        # ── Built-in (always available via ModelTrainer) ────────────────
        cls._registry["lightgbm"] = _LightGBMAdapter

        # ── GBDT (optional) ─────────────────────────────────────────────
        try:
            from app.services.model.xgboost_trainer import XGBoostTrainer
            cls._registry["xgboost"] = XGBoostTrainer
        except ImportError:
            pass

        try:
            from app.services.model.catboost_trainer import CatBoostTrainer
            cls._registry["catboost"] = CatBoostTrainer
        except ImportError:
            pass

        # ── sklearn (optional) ──────────────────────────────────────────
        try:
            from app.services.model.mlp_trainer import MLPTrainer
            cls._registry["mlp"] = MLPTrainer
        except ImportError:
            pass

        try:
            from app.services.model.linear_trainer import LinearTrainer
            cls._registry["ridge"] = lambda: LinearTrainer(model_type="ridge")
            cls._registry["lasso"] = lambda: LinearTrainer(model_type="lasso")
        except ImportError:
            pass

        # ── Deep learning (PyTorch required) ────────────────────────────
        try:
            from app.services.model.lstm_trainer import LSTMTrainer
            cls._registry["lstm"] = LSTMTrainer
        except ImportError:
            pass

        try:
            from app.services.model.gru_trainer import GRUTrainer
            cls._registry["gru"] = GRUTrainer
        except ImportError:
            pass

        try:
            from app.services.model.transformer_trainer import TransformerTrainer
            cls._registry["transformer"] = TransformerTrainer
        except ImportError:
            pass

        try:
            from app.services.model.tcn_trainer import TCNTrainer
            cls._registry["tcn"] = TCNTrainer
        except ImportError:
            pass

        try:
            from app.services.model.tabnet_trainer import TabNetTrainer
            cls._registry["tabnet"] = TabNetTrainer
        except ImportError:
            pass

        try:
            from app.services.model.simple_nn_trainer import SimpleNNTrainer
            cls._registry["simple_nn"] = SimpleNNTrainer
        except ImportError:
            pass

        # ── Ensemble ────────────────────────────────────────────────────
        try:
            from app.services.model.double_ensemble_trainer import DoubleEnsembleTrainer
            cls._registry["double_ensemble"] = DoubleEnsembleTrainer
        except ImportError:
            pass

    @classmethod
    def available_types(cls) -> list[str]:
        """Return the list of currently available model types."""
        if not cls._registry:
            cls._populate()
        return sorted(cls._registry)


# ---------------------------------------------------------------------------
# LightGBM adapter — delegates to ModelTrainer's existing logic
# ---------------------------------------------------------------------------


class _LightGBMAdapter:
    """Adapter that delegates to ModelTrainer's LightGBM methods.

    ModelFactory.create("lightgbm") returns this; the caller should use
    ModelTrainer methods directly.
    """

    def fit(self, X_train, y_train, X_valid, y_valid, config):
        from app.services.model.trainer import ModelTrainer
        return ModelTrainer().train_lightgbm(X_train, y_train, X_valid, y_valid, config)

    def predict(self, model, X):
        return model.predict(X, num_iteration=model.best_iteration)

    def get_feature_importance(self, model, feature_names):
        return dict(
            sorted(
                zip(feature_names, model.feature_importance(importance_type="gain")),
                key=lambda kv: kv[1],
                reverse=True,
            )
        )

    def save(self, model, path):
        model.save_model(path)

    def load(self, path):
        import lightgbm as lgb
        return lgb.Booster(model_file=path)
