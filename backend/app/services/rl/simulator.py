"""
RL Simulator: Gym-like environment for order execution.

Models the problem of slicing a large parent order into smaller child orders
over a fixed time horizon, with market impact and adverse selection.

Provides:
    Simulator (ABC)       Abstract base for RL environments.
    OrderExecutionSimulator  Concrete implementation for order execution.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class Simulator(ABC):
    """Abstract Gym-like RL environment."""

    @abstractmethod
    def reset(self) -> np.ndarray:
        """Reset the environment, return initial state."""

    @abstractmethod
    def step(self, action: int | float | np.ndarray) -> tuple[np.ndarray, float, bool, dict]:
        """Take an action, return (next_state, reward, done, info)."""

    @abstractmethod
    def seed(self, seed: int) -> None:
        """Set random seed."""


# ---------------------------------------------------------------------------
# Order Execution Simulator
# ---------------------------------------------------------------------------


@dataclass
class _OEConfig:
    """Internal configuration for OrderExecutionSimulator."""

    total_shares: int = 10000        # Total parent order size
    n_steps: int = 10               # Number of time steps (slices)
    price_impact: float = 0.05      # Temporary price impact per % of volume
    permanent_impact: float = 0.01  # Permanent price impact per % of volume
    risk_aversion: float = 0.1      # Risk aversion coefficient
    volatility: float = 0.02        # Price volatility per step (annualized / sqrt(252))
    init_price: float = 100.0       # Initial stock price


class OrderExecutionSimulator(Simulator):
    """Simulates slicing a parent order over discrete time steps.

    State space (6-dim):
        [0] remaining shares / total_shares (fraction)
        [1] time remaining / n_steps (fraction)
        [2] current price / init_price - 1 (relative price)
        [3] recent price momentum (short-term return)
        [4] volume pressure (recent volume / avg volume - 1)
        [5] cumulative shares executed / total_shares

    Action: fraction of remaining shares to execute this step (0 to 1).

    Reward: negative of execution cost (Implementation Shortfall).
    """

    def __init__(self, config: _OEConfig | None = None):
        self._cfg = config or _OEConfig()
        self._rng = np.random.RandomState(42)
        self._state: np.ndarray
        self._step_count: int
        self._remain: int
        self._price: float
        self._executed: int
        self._price_history: list[float]
        self._volume_history: list[float]

    # ------------------------------------------------------------------
    # Gym interface
    # ------------------------------------------------------------------

    def reset(self) -> np.ndarray:
        cfg = self._cfg
        self._step_count = 0
        self._remain = cfg.total_shares
        self._price = cfg.init_price
        self._executed = 0
        self._price_history = [cfg.init_price] * 10
        self._volume_history = [1000.0] * 10
        self._state = self._build_state()
        return self._state.copy()

    def step(self, action: float) -> tuple[np.ndarray, float, bool, dict]:
        """Execute *action* fraction of remaining shares.

        Parameters
        ----------
        action : float
            Fraction of remaining shares to execute (0 to 1). Clamped internally.

        Returns
        -------
        next_state : np.ndarray
        reward : float
        done : bool
        info : dict
        """
        cfg = self._cfg
        action = float(np.clip(action, 0.0, 1.0))

        # Shares to execute this step
        shares = int(self._remain * action)
        if self._step_count == cfg.n_steps - 1:
            shares = self._remain  # Force complete on last step

        if shares <= 0:
            shares = 1 if self._remain > 0 else 0

        # Market impact
        vol_pct = shares / cfg.total_shares
        temp_impact_cost = cfg.price_impact * vol_pct * self._price
        perm_impact = cfg.permanent_impact * vol_pct * self._price

        # Price moves: random walk + permanent impact
        price_noise = self._rng.randn() * cfg.volatility * self._price
        self._price += perm_impact + price_noise
        self._price = max(self._price, 0.01)

        # Execution price (average over the step)
        exec_price = self._price

        # Cost: Implementation Shortfall
        # IS = (exec_price - arrival_price) * shares + temp_impact
        arrival_price = self._price_history[-1]
        is_cost = (exec_price - arrival_price) * shares + temp_impact_cost

        # Reward: negative cost, normalized
        max_possible_cost = cfg.total_shares * cfg.price_impact * cfg.init_price
        reward = -is_cost / max(cfg.total_shares * cfg.init_price, 1e-6)

        # Optionally penalize remaining inventory risk
        if self._remain > 0:
            remaining_frac = self._remain / cfg.total_shares
            risk_penalty = cfg.risk_aversion * remaining_frac * cfg.volatility * self._price * self._remain
            reward -= risk_penalty / max(cfg.total_shares * cfg.init_price, 1e-6)

        # Update state
        self._executed += shares
        self._remain -= shares
        self._price_history.append(self._price)
        self._price_history.pop(0)
        self._volume_history.append(float(shares))
        self._volume_history.pop(0)
        self._step_count += 1

        self._state = self._build_state()
        done = self._step_count >= cfg.n_steps or self._remain <= 0

        info = {
            "step": self._step_count,
            "shares_executed": shares,
            "remain": self._remain,
            "price": self._price,
            "is_cost": is_cost,
            "reward": reward,
        }

        return self._state.copy(), reward, done, info

    def seed(self, seed: int) -> None:
        self._rng = np.random.RandomState(seed)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_state(self) -> np.ndarray:
        cfg = self._cfg
        remainder_pct = self._remain / max(cfg.total_shares, 1)
        time_pct = 1.0 - self._step_count / max(cfg.n_steps, 1)
        price_rel = self._price / cfg.init_price - 1.0
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
        executed_pct = self._executed / max(cfg.total_shares, 1)

        return np.array([
            remainder_pct,
            time_pct,
            price_rel,
            momentum,
            volume_pressure,
            executed_pct,
        ], dtype=np.float32)
