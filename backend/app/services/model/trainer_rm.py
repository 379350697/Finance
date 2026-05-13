"""
TrainerRM: multi-task trainer that jointly predicts multiple forward horizons.

Trains a shared-backbone model with task-specific heads for each horizon
(e.g., 1d, 5d, 10d, 20d returns). This encourages the shared backbone to
learn representations useful across multiple forecasting horizons.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import lightgbm as lgb
    _LGB_AVAILABLE = True
except ImportError:
    lgb = None
    _LGB_AVAILABLE = False

try:
    from scipy.stats import pearsonr, spearmanr
    _SCIPY_AVAILABLE = True
except ImportError:
    pearsonr = None
    spearmanr = None
    _SCIPY_AVAILABLE = False


class MultiTaskResult:
    """Result from multi-task training with per-horizon metrics."""

    def __init__(
        self,
        model_name: str,
        horizons: list[str],
        ic_means: dict[str, float],
        rank_ic_means: dict[str, float],
        icirs: dict[str, float],
        rank_icirs: dict[str, float],
        feature_importance: dict[str, float],
        model_paths: dict[str, str],
    ) -> None:
        self.model_name = model_name
        self.horizons = horizons
        self.ic_means = ic_means
        self.rank_ic_means = rank_ic_means
        self.icirs = icirs
        self.rank_icirs = rank_icirs
        self.feature_importance = feature_importance
        self.model_paths = model_paths


class TrainerRM:
    """Multi-task trainer that predicts N forward-return horizons jointly.

    Each horizon gets its own LightGBM model trained on the same factor data
    but with different label horizons. Feature importance is averaged across
    all task models.

    Parameters
    ----------
    horizons : list[str]
        Label types, e.g. ["next_ret1", "next_ret5", "next_ret10", "next_ret20"].
    trainer : ModelTrainer, optional
        If None, creates a default ModelTrainer.
    """

    def __init__(
        self,
        horizons: list[str] | None = None,
        trainer: Any = None,
    ) -> None:
        self.horizons = horizons or ["next_ret1", "next_ret5", "next_ret10", "next_ret20"]
        self._trainer = trainer

    @property
    def trainer(self) -> Any:
        if self._trainer is None:
            from app.services.model.trainer import ModelTrainer
            self._trainer = ModelTrainer()
        return self._trainer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(self, config: Any) -> MultiTaskResult:
        """Train one model per horizon, sharing the same factor data.

        Parameters
        ----------
        config : ModelTrainRequest-like
            Must have model_name, model_type, factor_set, date ranges,
            stock_pool, hyperparams.

        Returns
        -------
        MultiTaskResult
        """
        if not _LGB_AVAILABLE:
            raise RuntimeError("lightgbm is required for multi-task training.")
        if not _SCIPY_AVAILABLE:
            raise RuntimeError("scipy is required for IC computation.")

        ic_means: dict[str, float] = {}
        rank_ic_means: dict[str, float] = {}
        icirs: dict[str, float] = {}
        rank_icirs: dict[str, float] = {}
        model_paths: dict[str, str] = {}
        all_importances: list[dict[str, float]] = []

        from app.services.model.trainer import ModelConfig

        for horizon in self.horizons:
            logger.info("Training task: %s", horizon)

            task_config = ModelConfig(
                model_name=f"{config.model_name}_{horizon}",
                model_type=config.model_type,
                factor_set=config.factor_set,
                train_start=config.train_start,
                train_end=config.train_end,
                valid_start=config.valid_start,
                valid_end=config.valid_end,
                test_start=config.test_start,
                test_end=config.test_end,
                stock_pool=config.stock_pool,
                label_type=horizon,
                **getattr(config, "hyperparams", {}),
            )

            result = self.trainer.train(task_config)

            ic_means[horizon] = result.ic_mean
            rank_ic_means[horizon] = result.rank_ic_mean
            icirs[horizon] = result.icir
            rank_icirs[horizon] = result.rank_icir
            model_paths[horizon] = result.model_path
            all_importances.append(result.feature_importance)

        # Average feature importance across all tasks
        avg_importance = _average_importances(all_importances)

        return MultiTaskResult(
            model_name=config.model_name,
            horizons=self.horizons[:],
            ic_means=ic_means,
            rank_ic_means=rank_ic_means,
            icirs=icirs,
            rank_icirs=rank_icirs,
            feature_importance=avg_importance,
            model_paths=model_paths,
        )


def _average_importances(
    importances: list[dict[str, float]],
) -> dict[str, float]:
    """Average feature importance across multiple training runs."""
    if not importances:
        return {}

    all_features: set[str] = set()
    for imp in importances:
        all_features.update(imp.keys())

    avg: dict[str, float] = {}
    for feat in all_features:
        vals = [imp.get(feat, 0.0) for imp in importances]
        avg[feat] = sum(vals) / len(vals)

    return dict(
        sorted(avg.items(), key=lambda kv: kv[1], reverse=True)
    )
