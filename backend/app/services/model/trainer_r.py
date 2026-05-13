"""
TrainerR: rolling-window trainer with warm-start support.

Extends the standard ModelTrainer to train successive time windows where
each window initializes from the previous window's trained model (when
the model format supports it — GBDT models via continued training, NN
models via weight transfer).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.model.trainer import ModelConfig, ModelTrainer, ModelTrainResult

logger = logging.getLogger(__name__)


class WindowResult:
    """Result for a single rolling window."""

    def __init__(
        self,
        window_index: int,
        train_start: date,
        train_end: date,
        valid_start: date,
        valid_end: date,
        test_start: date,
        test_end: date,
        ic_mean: float = 0.0,
        icir: float = 0.0,
        rank_ic_mean: float = 0.0,
        rank_icir: float = 0.0,
        model_path: str = "",
    ) -> None:
        self.window_index = window_index
        self.train_start = train_start
        self.train_end = train_end
        self.valid_start = valid_start
        self.valid_end = valid_end
        self.test_start = test_start
        self.test_end = test_end
        self.ic_mean = ic_mean
        self.icir = icir
        self.rank_ic_mean = rank_ic_mean
        self.rank_icir = rank_icir
        self.model_path = model_path


class TrainerR:
    """Rolling-window trainer with incremental (warm-start) support.

    Each window trains a model; subsequent windows can optionally warm-start
    from the previous window's trained model.

    Parameters
    ----------
    trainer : ModelTrainer, optional
        If None, creates a default ModelTrainer.
    warm_start : bool
        If True, pass previous model as init_model to the next training run.
    """

    def __init__(self, trainer: Any = None, warm_start: bool = False) -> None:
        self._trainer = trainer
        self.warm_start = warm_start

    @property
    def trainer(self) -> ModelTrainer:
        if self._trainer is None:
            self._trainer = ModelTrainer()
        return self._trainer

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, config: Any) -> list[WindowResult]:
        """Execute rolling retraining over the configured date range.

        Parameters
        ----------
        config : RollingTrainRequest
            Contains model_type, factor_set, stock_pool, window_days,
            step_days, start_date, end_date, etc.

        Returns
        -------
        list[WindowResult]
        """
        windows = self._generate_windows(config)
        results: list[WindowResult] = []
        prev_model: Any = None

        for wi, (
            train_start, train_end,
            valid_start, valid_end,
            test_start, test_end,
        ) in enumerate(windows):
            logger.info(
                "TrainerR window %d: train=[%s,%s] valid=[%s,%s] test=[%s,%s]",
                wi, train_start, train_end, valid_start, valid_end, test_start, test_end,
            )
            try:
                win_result, prev_model = self._train_window(
                    config, wi,
                    train_start, train_end,
                    valid_start, valid_end,
                    test_start, test_end,
                    prev_model,
                )
                results.append(win_result)
            except Exception as exc:
                logger.error("TrainerR window %d failed: %s", wi, exc)
                prev_model = None
                results.append(WindowResult(
                    wi, train_start, train_end,
                    valid_start, valid_end,
                    test_start, test_end,
                ))

        return results

    # ------------------------------------------------------------------
    # Window generation
    # ------------------------------------------------------------------

    def _generate_windows(
        self, config: Any,
    ) -> list[tuple[date, date, date, date, date, date]]:
        """Generate window boundaries with train/valid/test split."""
        start = config.start_date
        end = config.end_date
        window_days = config.window_days
        step_days = config.step_days
        min_train = getattr(config, "min_train_days", 120)

        if window_days <= 0 or step_days <= 0:
            logger.warning("Invalid window/step days; returning empty.")
            return []
        if start is None or end is None:
            logger.warning("start_date or end_date is None; returning empty.")
            return []

        total_days = (end - start).days
        if total_days < window_days:
            logger.warning("Range too short for window_days=%d.", window_days)
            return []

        windows: list[tuple[date, date, date, date, date, date]] = []
        win_start = start
        while win_start + timedelta(days=window_days) <= end:
            win_end = win_start + timedelta(days=window_days)
            train_days = int(window_days * 0.6)
            valid_days = int(window_days * 0.2)

            train_end_dt = win_start + timedelta(days=train_days)
            valid_end_dt = train_end_dt + timedelta(days=valid_days)

            if train_days < min_train:
                win_start += timedelta(days=step_days)
                continue

            windows.append((
                win_start, train_end_dt,
                train_end_dt + timedelta(days=1), valid_end_dt,
                valid_end_dt + timedelta(days=1), win_end,
            ))
            win_start += timedelta(days=step_days)

        logger.info("TrainerR: %d windows generated.", len(windows))
        return windows

    # ------------------------------------------------------------------
    # Single window training
    # ------------------------------------------------------------------

    def _train_window(
        self,
        config: Any,
        wi: int,
        train_start: date,
        train_end: date,
        valid_start: date,
        valid_end: date,
        test_start: date,
        test_end: date,
        prev_model: Any,
    ) -> tuple[WindowResult, Any]:
        win_config = ModelConfig(
            model_name=f"{config.base_model_name}_w{wi}",
            model_type=config.model_type,
            factor_set=config.factor_set,
            train_start=train_start,
            train_end=train_end,
            valid_start=valid_start,
            valid_end=valid_end,
            test_start=test_start,
            test_end=test_end,
            stock_pool=config.stock_pool,
            label_type=config.label_type,
            **getattr(config, "hyperparams", {}),
        )

        # If warm_start is enabled and we have a previous model, try to
        # pass it as init_model. Only supported for GBDT model types.
        if self.warm_start and prev_model is not None:
            _try_warm_start(win_config, prev_model)

        result = self.trainer.train(win_config)

        # Load the newly saved model as warm-start base for next window
        model = _load_model_safe(result.model_path, config.model_type)

        win_result = WindowResult(
            window_index=wi,
            train_start=train_start,
            train_end=train_end,
            valid_start=valid_start,
            valid_end=valid_end,
            test_start=test_start,
            test_end=test_end,
            ic_mean=result.ic_mean,
            icir=result.icir,
            rank_ic_mean=result.rank_ic_mean,
            rank_icir=result.rank_icir,
            model_path=str(result.model_path),
        )
        return win_result, model


def _try_warm_start(config: ModelConfig, prev_model: Any) -> None:
    """Attempt to attach previous model as init_model for GBDT types."""
    if config.model_type in ("lightgbm", "xgboost", "catboost"):
        config.__dict__.setdefault("init_model", prev_model)


def _load_model_safe(path_str: str, model_type: str) -> Any:
    """Load model from path without raising on failure."""
    try:
        if model_type == "lightgbm":
            import lightgbm as lgb
            return lgb.Booster(model_file=path_str)
        elif model_type == "xgboost":
            import xgboost as xgb
            return xgb.Booster(model_file=path_str)
        elif model_type == "catboost":
            from catboost import CatBoost
            return CatBoost().load_model(path_str)
    except Exception:
        pass
    return None
