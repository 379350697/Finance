"""
DoubleEnsemble: two-layer stacking ensemble.

Layer 1: 3 GBDT models (LightGBM/XGBoost/CatBoost) trained independently.
Layer 2: Linear meta-model that combines L1 predictions.

Implements BaseModel interface.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from app.services.model.base import BaseModel

logger = logging.getLogger(__name__)

# Try importing base model trainers
try:
    from app.services.model.trainer import ModelTrainer, ModelConfig
    _LGB_AVAILABLE = True
except ImportError:
    _LGB_AVAILABLE = False

try:
    from sklearn.linear_model import Ridge
    _SKLEARN_AVAILABLE = True
except ImportError:
    Ridge = None  # type: ignore[assignment]
    _SKLEARN_AVAILABLE = False


class DoubleEnsembleTrainer(BaseModel):
    """Two-layer stacking ensemble.

    Layer 1: trains LightGBM + XGBoost + CatBoost (whichever are available).
    Layer 2: Ridge regression meta-model on L1 predictions.

    Requires at least 2 L1 models available.
    """

    def __init__(self):
        self._l1_models: list[Any] = []
        self._l1_names: list[str] = []
        self._meta: Any = None  # Ridge

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
    ) -> DoubleEnsembleTrainer:
        """Train the two-layer ensemble."""
        if not _SKLEARN_AVAILABLE:
            raise RuntimeError("scikit-learn is required for DoubleEnsemble.")

        # ── Layer 1: train individual GBDT models ────────────────────────
        base_trainer = ModelTrainer() if _LGB_AVAILABLE else None

        l1_preds_valid: list[np.ndarray] = []
        l1_preds_train: list[np.ndarray] = []

        # LightGBM
        if _LGB_AVAILABLE and base_trainer is not None:
            try:
                lgb_model, lgb_pred_v = self._train_l1(
                    base_trainer, X_train, y_train, X_valid, y_valid, config, "lightgbm"
                )
                self._l1_models.append(lgb_model)
                self._l1_names.append("lightgbm")
                l1_preds_valid.append(lgb_pred_v)
                l1_preds_train.append(
                    base_trainer.predict(lgb_model, X_train)
                )
                logger.info("DoubleEnsemble L1: lightgbm trained")
            except Exception as e:
                logger.warning("DoubleEnsemble L1 lightgbm failed: %s", e)

        # XGBoost
        try:
            from app.services.model.xgboost_trainer import XGBoostTrainer
            xgb = XGBoostTrainer()
            xgb_model = xgb.fit(X_train, y_train, X_valid, y_valid, config)
            self._l1_models.append(xgb_model)
            self._l1_names.append("xgboost")
            l1_preds_valid.append(xgb.predict(xgb_model, X_valid))
            l1_preds_train.append(xgb.predict(xgb_model, X_train))
            logger.info("DoubleEnsemble L1: xgboost trained")
        except Exception as e:
            logger.warning("DoubleEnsemble L1 xgboost failed: %s", e)

        # CatBoost
        try:
            from app.services.model.catboost_trainer import CatBoostTrainer
            cb = CatBoostTrainer()
            cb_model = cb.fit(X_train, y_train, X_valid, y_valid, config)
            self._l1_models.append(cb_model)
            self._l1_names.append("catboost")
            l1_preds_valid.append(cb.predict(cb_model, X_valid))
            l1_preds_train.append(cb.predict(cb_model, X_train))
            logger.info("DoubleEnsemble L1: catboost trained")
        except Exception as e:
            logger.warning("DoubleEnsemble L1 catboost failed: %s", e)

        if len(self._l1_models) < 2:
            raise RuntimeError(
                f"DoubleEnsemble needs at least 2 L1 models, got {len(self._l1_models)}"
            )

        # ── Layer 2: Ridge meta-model ────────────────────────────────────
        Z_train = np.column_stack(l1_preds_train)
        Z_valid = np.column_stack(l1_preds_valid)

        self._meta = Ridge(alpha=1.0)
        self._meta.fit(Z_train, y_train)

        logger.info("DoubleEnsemble L2 (Ridge) trained on %d L1 models", len(self._l1_models))
        return self

    def _train_l1(
        self,
        base_trainer: Any,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_valid: np.ndarray,
        y_valid: np.ndarray,
        config: Any,
        model_type: str,
    ) -> tuple[Any, np.ndarray]:
        """Train a single L1 model and return (model, valid_predictions)."""
        l1_config = ModelConfig(
            model_name="de_l1",
            model_type=model_type,
            factor_set=getattr(config, "factor_set", "alpha158"),
            train_start=getattr(config, "train_start", None),
            train_end=getattr(config, "train_end", None),
            valid_start=getattr(config, "valid_start", None),
            valid_end=getattr(config, "valid_end", None),
            test_start=getattr(config, "test_start", None),
            test_end=getattr(config, "test_end", None),
            stock_pool=getattr(config, "stock_pool", []),
            label_type=getattr(config, "label_type", "next_ret5"),
            seed=getattr(config, "seed", 42),
        )

        base_trainer_obj = base_trainer._get_trainer(model_type)
        model = base_trainer_obj.fit(X_train, y_train, X_valid, y_valid, l1_config)
        preds_v = base_trainer_obj.predict(model, X_valid)
        return model, preds_v

    def predict(self, model: Any, X: np.ndarray) -> np.ndarray:
        """Generate ensemble predictions."""
        l1_preds: list[np.ndarray] = []

        # L1 predictions from each model
        for i, name in enumerate(self._l1_names):
            if name == "lightgbm":
                from app.services.model.trainer import ModelTrainer
                bt = ModelTrainer()
                p = bt.predict(self._l1_models[i], X)
            elif name == "xgboost":
                from app.services.model.xgboost_trainer import XGBoostTrainer
                p = XGBoostTrainer().predict(self._l1_models[i], X)
            elif name == "catboost":
                from app.services.model.catboost_trainer import CatBoostTrainer
                p = CatBoostTrainer().predict(self._l1_models[i], X)
            else:
                continue
            l1_preds.append(p)

        Z = np.column_stack(l1_preds)

        # L2 meta-model prediction
        return self._meta.predict(Z)

    def get_feature_importance(
        self, model: Any, feature_names: list[str]
    ) -> dict[str, float]:
        """Return ensemble feature importance (averaged across L1 models)."""
        all_imp: dict[str, list[float]] = {f: [] for f in feature_names}
        from app.services.model.trainer import ModelTrainer

        for i, name in enumerate(self._l1_names):
            try:
                if name == "lightgbm":
                    bt = ModelTrainer()
                    imp = bt.get_feature_importance(self._l1_models[i], feature_names)
                elif name == "xgboost":
                    from app.services.model.xgboost_trainer import XGBoostTrainer
                    imp = XGBoostTrainer().get_feature_importance(
                        self._l1_models[i], feature_names
                    )
                elif name == "catboost":
                    from app.services.model.catboost_trainer import CatBoostTrainer
                    imp = CatBoostTrainer().get_feature_importance(
                        self._l1_models[i], feature_names
                    )
                else:
                    continue
                for f, v in imp.items():
                    all_imp[f].append(v)
            except Exception:
                pass

        return dict(
            sorted(
                ((f, np.mean(v)) for f, v in all_imp.items() if v),
                key=lambda kv: -kv[1],
            )
        )

    def save(self, model: Any, path: str) -> None:
        import joblib
        data = {
            "l1_models": self._l1_models,
            "l1_names": self._l1_names,
            "meta": self._meta,
        }
        joblib.dump(data, path)

    def load(self, path: str) -> Any:
        import joblib
        data = joblib.load(path)
        trainer = DoubleEnsembleTrainer()
        trainer._l1_models = data["l1_models"]
        trainer._l1_names = data["l1_names"]
        trainer._meta = data["meta"]
        return trainer
