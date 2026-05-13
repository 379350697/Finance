"""
RollingRetrainer: sliding-window model retraining with IC decay tracking.

Trains models on rolling windows to measure performance stability
and detect alpha decay over time.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.core.config import settings

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


class RollingRetrainer:
    """Train models on rolling windows and track performance decay.

    Usage::

        retrainer = RollingRetrainer()
        results = retrainer.run(RollingTrainRequest(
            base_model_name="lgb_alpha158",
            model_type="lightgbm",
            factor_set="alpha158",
            stock_pool=["000001", "000002"],
            window_days=252, step_days=21,
            start_date=date(2020,1,1), end_date=date(2023,12,31),
        ))
    """

    def __init__(self, trainer: Any = None) -> None:
        self._trainer = trainer

    @property
    def trainer(self) -> Any:
        if self._trainer is None:
            from app.services.model.trainer import ModelTrainer

            self._trainer = ModelTrainer()
        return self._trainer

    def run(self, config: Any) -> list[WindowResult]:
        """Execute rolling retraining over the configured date range.

        Delegates to TrainerR for window generation and training,
        keeping this class's API for backward compatibility.

        Returns list of WindowResult, one per window.
        """
        try:
            from app.services.model.trainer_r import TrainerR
            trainer_r = TrainerR(trainer=self.trainer)
            raw_results = trainer_r.run(config)
            # Convert TrainerR.WindowResult -> local WindowResult
            return [
                WindowResult(
                    window_index=r.window_index,
                    train_start=r.train_start,
                    train_end=r.train_end,
                    valid_start=r.valid_start,
                    valid_end=r.valid_end,
                    test_start=r.test_start,
                    test_end=r.test_end,
                    ic_mean=r.ic_mean,
                    icir=r.icir,
                    rank_ic_mean=r.rank_ic_mean,
                    rank_icir=r.rank_icir,
                    model_path=r.model_path,
                )
                for r in raw_results
            ]
        except ImportError:
            logger.debug("TrainerR not available, using built-in window logic.")

        windows = self._generate_windows(config)
        results: list[WindowResult] = []
        for wi, (
            train_start,
            train_end,
            valid_start,
            valid_end,
            test_start,
            test_end,
        ) in enumerate(windows):
            logger.info(
                "Window %d: train=[%s,%s] valid=[%s,%s] test=[%s,%s]",
                wi,
                train_start,
                train_end,
                valid_start,
                valid_end,
                test_start,
                test_end,
            )
            try:
                win_result = self._train_window(
                    config,
                    wi,
                    train_start,
                    train_end,
                    valid_start,
                    valid_end,
                    test_start,
                    test_end,
                )
                results.append(win_result)
            except Exception as exc:
                logger.error("Window %d failed: %s", wi, exc)
                results.append(
                    WindowResult(
                        wi,
                        train_start,
                        train_end,
                        valid_start,
                        valid_end,
                        test_start,
                        test_end,
                    )
                )
        return results

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
    ) -> WindowResult:
        from app.services.model.trainer import ModelConfig

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
            **config.hyperparams,
        )
        result = self.trainer.train(win_config)
        return WindowResult(
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

    def _generate_windows(self, config: Any) -> list[tuple[date, date, date, date, date, date]]:
        """Generate (train_start, train_end, valid_start, valid_end,
        test_start, test_end) tuples for each rolling window.

        Each window spans window_days calendar days, stepping by step_days.
        Within each window:
          - train: first 60% of the window
          - valid: next 20%
          - test:  final 20%

        Edge cases handled:
          - Windows shorter than min_train_days are skipped.
          - Ranges too short for any window produce an empty list.
          - Overlapping windows are expected and supported.
        """
        start = config.start_date
        end = config.end_date
        window_days = config.window_days
        step_days = config.step_days
        min_train = getattr(config, "min_train_days", 120)

        train_ratio = 0.6
        valid_ratio = 0.2

        # Guard: window_days and step_days must be positive
        if window_days <= 0 or step_days <= 0:
            logger.warning(
                "Invalid window_days=%d or step_days=%d; returning empty window list.",
                window_days,
                step_days,
            )
            return []

        # Guard: start/end must be valid
        if start is None or end is None:
            logger.warning("start_date or end_date is None; returning empty window list.")
            return []

        # Guard: range must be long enough for at least one window
        total_days = (end - start).days
        if total_days < window_days:
            logger.warning(
                "Date range [%s, %s] is %d days, shorter than window_days=%d. "
                "No windows can be generated.",
                start,
                end,
                total_days,
                window_days,
            )
            return []

        windows: list[tuple[date, date, date, date, date, date]] = []
        win_start = start
        while win_start + timedelta(days=window_days) <= end:
            win_end = win_start + timedelta(days=window_days)
            train_days = int(window_days * train_ratio)
            valid_days = int(window_days * valid_ratio)

            train_end_dt = win_start + timedelta(days=train_days)
            valid_end_dt = train_end_dt + timedelta(days=valid_days)

            if train_days < min_train:
                logger.debug(
                    "Skipping window starting %s: train_days=%d < min_train=%d",
                    win_start,
                    train_days,
                    min_train,
                )
                win_start += timedelta(days=step_days)
                continue

            windows.append(
                (
                    win_start,
                    train_end_dt,
                    train_end_dt + timedelta(days=1),
                    valid_end_dt,
                    valid_end_dt + timedelta(days=1),
                    win_end,
                )
            )
            win_start += timedelta(days=step_days)

        logger.info(
            "Generated %d rolling windows from %s to %s (window=%dd, step=%dd).",
            len(windows),
            start,
            end,
            window_days,
            step_days,
        )
        return windows
