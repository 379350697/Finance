"""
NumpyOrderIndicator: vectorized trade-eligibility checks.

Eliminates per-stock Python loops for common backtest guard conditions:
    - Limit-up/down checks (can't buy limit-up, can't sell limit-down)
    - Suspension checks
    - Volume-based capacity checks
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np


class NumpyOrderIndicator:
    """Vectorized trading indicator computer.

    Parameters
    ----------
    nq : NumpyQuote
        The quote store providing the underlying bar data.
    """

    def __init__(self, nq: Any):
        self._nq = nq

    # ------------------------------------------------------------------
    # Single-stock checks (still fast — indexed lookup)
    # ------------------------------------------------------------------

    def is_limit_up(self, code: str, dt: date) -> bool:
        """Check if *code* hit limit-up on *dt*."""
        bar = self._nq.get_at(code, dt)
        if bar is None:
            return False
        return bool(bar["is_limit_up"])

    def is_limit_down(self, code: str, dt: date) -> bool:
        """Check if *code* hit limit-down on *dt*."""
        bar = self._nq.get_at(code, dt)
        if bar is None:
            return False
        return bool(bar["is_limit_down"])

    def is_suspended(self, code: str, dt: date) -> bool:
        """Check if *code* is suspended on *dt*."""
        bar = self._nq.get_at(code, dt)
        if bar is None:
            return True  # no data = assume suspended
        return bool(bar["is_suspended"])

    def can_buy(self, code: str, dt: date) -> bool:
        """Can we buy *code* on *dt*? (not limit-up, not suspended)."""
        bar = self._nq.get_at(code, dt)
        if bar is None:
            return False
        return not (bar["is_limit_up"] or bar["is_suspended"])

    def can_sell(self, code: str, dt: date) -> bool:
        """Can we sell *code* on *dt*? (not limit-down, not suspended)."""
        bar = self._nq.get_at(code, dt)
        if bar is None:
            return False
        return not (bar["is_limit_down"] or bar["is_suspended"])

    # ------------------------------------------------------------------
    # Vectorized cross-sectional checks
    # ------------------------------------------------------------------

    def can_buy_all(self, codes: list[str], dt: date) -> np.ndarray:
        """Return bool array of buy eligibility for all *codes* on *dt*."""
        closes = self._nq.get_field("close", codes, dt)
        # A stock is buyable if it has a valid close > 0
        return (~np.isnan(closes)) & (closes > 0)

    def buy_volume(self, codes: list[str], dt: date) -> np.ndarray:
        """Return volume for all *codes* on *dt*."""
        return self._nq.get_field("volume", codes, dt)

    def sell_volume(self, codes: list[str], dt: date) -> np.ndarray:
        """Return volume for all *codes* on *dt* (same as buy for now)."""
        return self._nq.get_field("volume", codes, dt)

    def close_prices(self, codes: list[str], dt: date) -> np.ndarray:
        """Return close prices for all *codes* on *dt*."""
        return self._nq.get_field("close", codes, dt)

    def premarket_prices(self, codes: list[str], dt: date) -> np.ndarray:
        """Return open prices (used as entry/exit reference)."""
        return self._nq.get_field("open", codes, dt)
