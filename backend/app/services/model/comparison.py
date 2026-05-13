"""ModelComparator: train all supported models and compare."""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ModelComparator:
    """Trains multiple model types on the same data and compares metrics.

    Usage::

        from app.services.model.trainer import ModelConfig, ModelTrainer
        from app.services.model.comparison import ModelComparator

        comparator = ModelComparator(ModelTrainer())
        results = comparator.compare(config, model_types=["lightgbm", "xgboost"])
    """

    def __init__(self, trainer: Any) -> None:
        self.trainer = trainer

    def compare(
        self,
        config: Any,
        model_types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Train each requested model type and collect metrics.

        Parameters
        ----------
        config : ModelConfig
            Base configuration.  ``model_type`` and ``model_name`` are
            overridden per-run so each model is saved to a distinct file.
        model_types : list[str] or None
            Model types to train.  Defaults to all four supported types.

        Returns
        -------
        list[dict]
            One dictionary per model type with keys: model_type, ic_mean,
            ic_std, icir, rank_ic_mean, rank_icir, mse, mae,
            train_time_seconds, status.  Failed runs have status "failed"
            and include an "error" key.
        """
        model_types = model_types or ["lightgbm", "xgboost", "catboost", "mlp"]
        results: list[dict[str, Any]] = []

        for mt in model_types:
            try:
                cfg = config.copy(update={"model_type": mt, "model_name": f"{config.model_name}_{mt}"})
                t0 = time.time()
                result = self.trainer.train(cfg)
                elapsed = round(time.time() - t0, 2)
                results.append({
                    "model_type": mt,
                    "ic_mean": result.ic_mean,
                    "ic_std": result.ic_std,
                    "icir": result.icir,
                    "rank_ic_mean": result.rank_ic_mean,
                    "rank_icir": result.rank_icir,
                    "mse": result.mse,
                    "mae": result.mae,
                    "train_time_seconds": elapsed,
                    "status": "completed",
                })
                logger.info(
                    "Model type %s completed in %.1fs (ICIR=%.4f)",
                    mt, elapsed, result.icir,
                )
            except ImportError:
                logger.warning("Skipping %s: not installed", mt)
                results.append({
                    "model_type": mt,
                    "status": "failed",
                    "error": f"{mt} is not installed",
                })
            except Exception as exc:
                logger.error("Failed %s: %s", mt, exc)
                results.append({
                    "model_type": mt,
                    "status": "failed",
                    "error": str(exc),
                })

        return results
