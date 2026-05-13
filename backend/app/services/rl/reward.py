"""
Reward functions for RL training.

Provides:
    Reward (ABC)
    ExecutionCostReward     Implementation Shortfall based.
    RiskAdjustedReward      IS + risk penalty.
    ISReward                Pure Implementation Shortfall reward.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class Reward(ABC):
    """Abstract reward function."""

    @abstractmethod
    def compute(self, info: dict[str, Any]) -> float:
        """Compute reward from environment info dict."""


class ExecutionCostReward(Reward):
    """Reward based on negative execution cost (Implementation Shortfall).

    reward = -(exec_price - arrival_price) * shares / normalization
             - temp_impact / normalization
    """

    def __init__(
        self,
        total_shares: int = 10000,
        init_price: float = 100.0,
        price_impact: float = 0.05,
        risk_aversion: float = 0.1,
        volatility: float = 0.02,
    ):
        self.total_shares = total_shares
        self.init_price = init_price
        self.price_impact = price_impact
        self.risk_aversion = risk_aversion
        self.volatility = volatility
        self._norm = total_shares * init_price

    def compute(self, info: dict[str, Any]) -> float:
        is_cost = float(info.get("is_cost", 0))
        remain = int(info.get("remain", 0))
        price = float(info.get("price", self.init_price))

        reward = -is_cost / max(self._norm, 1e-6)

        # Risk penalty for unexecuted shares
        if remain > 0:
            remaining_frac = remain / max(self.total_shares, 1)
            risk_penalty = (
                self.risk_aversion
                * remaining_frac
                * self.volatility
                * price
                * remain
            )
            reward -= risk_penalty / max(self._norm, 1e-6)

        return float(reward)


class RiskAdjustedReward(Reward):
    """Reward with configurable risk-return trade-off.

    reward = alpha * execution_reward - (1-alpha) * risk_penalty
    """

    def __init__(
        self,
        total_shares: int = 10000,
        init_price: float = 100.0,
        alpha: float = 0.7,
        price_impact: float = 0.05,
        volatility: float = 0.02,
    ):
        self.total_shares = total_shares
        self.init_price = init_price
        self.alpha = alpha
        self.price_impact = price_impact
        self.volatility = volatility
        self._norm = total_shares * init_price

    def compute(self, info: dict[str, Any]) -> float:
        is_cost = float(info.get("is_cost", 0))
        remain = int(info.get("remain", 0))
        price = float(info.get("price", self.init_price))

        exec_reward = -is_cost / max(self._norm, 1e-6)

        risk_penalty = 0.0
        if remain > 0:
            remaining_frac = remain / max(self.total_shares, 1)
            risk_penalty = (
                self.volatility * price * remaining_frac * remain
            ) / max(self._norm, 1e-6)

        return self.alpha * exec_reward - (1 - self.alpha) * risk_penalty


class ISReward(Reward):
    """Pure Implementation Shortfall reward: no risk penalty.

    reward = -(exec_price - arrival_price) * shares / notional
    """

    def __init__(self, total_shares: int = 10000, init_price: float = 100.0):
        self.total_shares = total_shares
        self.init_price = init_price
        self._norm = total_shares * init_price

    def compute(self, info: dict[str, Any]) -> float:
        is_cost = float(info.get("is_cost", 0))
        return -is_cost / max(self._norm, 1e-6)
