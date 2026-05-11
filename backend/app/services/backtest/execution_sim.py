"""
ExecutionSimulator: simulates trade execution with slippage, market impact,
and transaction costs for backtesting.

Uses fee rates from ``app.core.config.settings``.
"""

from __future__ import annotations

import math
import random

from app.core.config import settings


class ExecutionSimulator:
    """Simulates execution-level frictions in backtesting.

    Models:
    - Gaussian slippage: price * (1 +- N(0, slippage_std))
    - Market impact: price * (1 + impact_coef * sqrt(qty / avg_vol))
    - Transaction costs: commission, stamp tax (sell only), transfer fee

    Parameters
    ----------
    slippage_std : float
        Standard deviation of slippage noise (default 0.001 = 0.1%).
    impact_coef : float
        Market impact coefficient (default 1e-8).
    """

    def __init__(
        self,
        slippage_std: float = 0.001,
        impact_coef: float = 1e-8,
    ) -> None:
        self._slippage_std = slippage_std
        self._impact_coef = impact_coef

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def entry_price(
        self, desired: float, qty: float, avg_vol: float
    ) -> float:
        """Compute buy fill price.

        entry_price = desired * (1 + noise + impact)

        Parameters
        ----------
        desired : float
            Desired entry price (e.g. next-day open).
        qty : float
            Number of shares to buy.
        avg_vol : float
            Average daily volume, used for impact calculation.
        """
        noise = abs(random.gauss(0, self._slippage_std))
        impact = self._impact(qty, avg_vol)
        return desired * (1 + noise + impact)

    def exit_price(
        self, desired: float, qty: float, avg_vol: float
    ) -> float:
        """Compute sell fill price.

        exit_price = desired * (1 - noise - impact)

        Parameters
        ----------
        desired : float
            Desired exit price (e.g. exit-day open).
        qty : float
            Number of shares to sell.
        avg_vol : float
            Average daily volume, used for impact calculation.
        """
        noise = abs(random.gauss(0, self._slippage_std))
        impact = self._impact(qty, avg_vol)
        return desired * (1 - noise - impact)

    def transaction_cost(
        self, price: float, qty: float, side: str
    ) -> float:
        """Calculate transaction costs for a trade.

        Components:
        - Commission (buy and sell): commission_rate * price * qty, min_commission floor
        - Stamp tax (sell only): stamp_tax_rate * price * qty
        - Transfer fee (buy and sell): transfer_fee_rate * price * qty

        Returns
        -------
        float
            Total cost in CNY (always non-negative).
        """
        turnover = price * qty

        # Commission with minimum floor
        commission = max(
            settings.commission_rate * turnover,
            settings.min_commission,
        )

        # Stamp tax (sell only)
        stamp_tax = 0.0
        if side == "sell":
            stamp_tax = settings.stamp_tax_rate * turnover

        # Transfer fee
        transfer_fee = settings.transfer_fee_rate * turnover

        return commission + stamp_tax + transfer_fee

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _impact(self, qty: float, avg_vol: float) -> float:
        """Compute market impact ratio.

        Uses the square-root model: impact_coef * sqrt(qty / avg_vol).
        If avg_vol is 0 or very small, returns 0 to avoid division issues.
        """
        if avg_vol is None or avg_vol <= 0 or qty <= 0:
            return 0.0
        ratio = qty / avg_vol
        return self._impact_coef * math.sqrt(ratio)
