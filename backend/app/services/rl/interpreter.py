"""
StateInterpreter: transforms raw market data into RL observation vectors.

Provides:
    StateInterpreter (ABC)
    ExecutionStateInterpreter  Order-execution-specific state builder.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class StateInterpreter(ABC):
    """Transforms market/meta data into a fixed-dim observation vector."""

    @abstractmethod
    def build_state(self, raw_data: dict[str, Any]) -> np.ndarray:
        """Build observation vector from raw data."""

    @abstractmethod
    def state_dim(self) -> int:
        """Return the dimension of the state vector."""


class ExecutionStateInterpreter(StateInterpreter):
    """Builds 6-dim state vectors for order execution.

    Features:
        [0] remaining_qty / total_qty
        [1] remaining_time / total_time
        [2] current_price / arrival_price - 1
        [3] price_momentum (5-step)
        [4] volume_pressure
        [5] executed_qty / total_qty
    """

    def __init__(
        self,
        total_shares: int = 10000,
        n_steps: int = 10,
        init_price: float = 100.0,
    ):
        self.total_shares = total_shares
        self.n_steps = n_steps
        self.init_price = init_price
        self._price_history: list[float] = [init_price] * 10
        self._volume_history: list[float] = [1000.0] * 10

    def state_dim(self) -> int:
        return 6

    def build_state(self, raw_data: dict[str, Any]) -> np.ndarray:
        """Build state from market data dict.

        Expected keys:
            remain, step_count, current_price, executed
        """
        remain = float(raw_data.get("remain", self.total_shares))
        step = int(raw_data.get("step_count", 0))
        price = float(raw_data.get("current_price", self.init_price))
        executed = float(raw_data.get("executed", 0))
        volume = float(raw_data.get("volume", 0))

        # Update histories
        self._price_history.append(price)
        self._price_history.pop(0)
        self._volume_history.append(volume)
        self._volume_history.pop(0)

        remain_pct = remain / max(self.total_shares, 1)
        time_pct = 1.0 - step / max(self.n_steps, 1)
        price_rel = price / self.init_price - 1.0

        momentum = (
            self._price_history[-1] / max(self._price_history[-5], 1e-6) - 1.0
            if len(self._price_history) >= 5
            else 0.0
        )

        volume_pressure = (
            self._volume_history[-1] / max(np.mean(self._volume_history[-5:]), 1e-6) - 1.0
            if len(self._volume_history) >= 5
            else 0.0
        )

        executed_pct = executed / max(self.total_shares, 1)

        return np.array([
            remain_pct,
            time_pct,
            price_rel,
            momentum,
            volume_pressure,
            executed_pct,
        ], dtype=np.float32)

    def reset(self) -> None:
        """Reset history buffers."""
        self._price_history = [self.init_price] * 10
        self._volume_history = [1000.0] * 10
