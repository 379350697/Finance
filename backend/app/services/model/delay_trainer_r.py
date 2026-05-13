"""
DelayTrainerR: delay-aware rolling trainer.

Offsets feature (factor) dates by a configurable number of trading days
relative to label dates. This simulates real-world prediction latency:
factors are computed on day T but trading decisions execute on T+delay.

Extends TrainerR with a delay parameter that shifts the effective training
data window backward.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from app.services.model.trainer_r import TrainerR, WindowResult

logger = logging.getLogger(__name__)


class DelayTrainerR(TrainerR):
    """Rolling trainer with configurable feature-label date offset.

    In production, factor data is available with some delay (e.g., computed
    after market close and available next morning). This trainer shifts the
    training windows backward by *delay_days* so the model learns on data
    that would actually have been available at decision time.

    Parameters
    ----------
    delay_days : int
        Number of calendar days to offset features before labels.
        Default 1 (factors available next trading day).
    trainer : ModelTrainer, optional
    warm_start : bool
        Passed through to TrainerR.
    """

    def __init__(
        self,
        delay_days: int = 1,
        trainer: Any = None,
        warm_start: bool = False,
    ) -> None:
        super().__init__(trainer=trainer, warm_start=warm_start)
        if delay_days < 0:
            raise ValueError(f"delay_days must be >= 0, got {delay_days}")
        self.delay_days = delay_days

    # ------------------------------------------------------------------
    # Override window generation to apply delay offset
    # ------------------------------------------------------------------

    def _generate_windows(
        self, config: Any,
    ) -> list[tuple[date, date, date, date, date, date]]:
        """Generate windows shifted backward by delay_days."""
        original = super()._generate_windows(config)

        if self.delay_days <= 0:
            return original

        shifted: list[tuple[date, date, date, date, date, date]] = []
        delta = timedelta(days=self.delay_days)

        for train_start, train_end, valid_start, valid_end, test_start, test_end in original:
            shifted.append((
                train_start - delta,
                train_end - delta,
                valid_start - delta,
                valid_end - delta,
                test_start - delta,
                test_end - delta,
            ))

        logger.info(
            "DelayTrainerR: %d windows shifted by %d days.",
            len(shifted),
            self.delay_days,
        )
        return shifted
