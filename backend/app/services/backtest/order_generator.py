"""
OrderGenerator: abstract order generation from signals and portfolio state.

Provides:
    Order           Dataclass for a single order (buy/sell/qty/price limit).
    OrderGenerator  ABC with generate().
    OrderGenWInteract   Generates paired buy/sell orders respecting existing
                        positions — replace what changed.
    OrderGenWOInteract  Generates buy/sell orders independently, ignoring
                        existing positions.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """A single order generated from a signal."""

    code: str
    date: date
    direction: str  # "buy" or "sell"
    quantity: float
    price_limit: float | None = None  # None = market order
    signal_score: float = 0.0
    reason: str = ""

    def __post_init__(self):
        if self.direction not in ("buy", "sell"):
            raise ValueError(f"direction must be 'buy' or 'sell', got {self.direction!r}")


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class OrderGenerator(ABC):
    """Abstract base for order generation strategies."""

    @abstractmethod
    def generate(
        self,
        signals: dict[str, float],          # code -> score
        current_positions: dict[str, dict],  # code -> {entry_price, qty, ...}
        dt: date,
        available_codes: list[str],
        max_positions: int = 50,
    ) -> list[Order]:
        """Generate orders from signals and current portfolio state.

        Parameters
        ----------
        signals : dict
            Code -> model score. Higher scores = stronger buy signal.
        current_positions : dict
            Currently held positions keyed by code.
        dt : date
            Trading date for which orders are generated.
        available_codes : list[str]
            All codes eligible for trading.
        max_positions : int
            Maximum number of positions allowed.

        Returns
        -------
        list[Order]
        """


# ---------------------------------------------------------------------------
# Concrete implementations
# ---------------------------------------------------------------------------


class OrderGenWInteract(OrderGenerator):
    """Order generation WITH interaction — aware of existing positions.

    For each code currently held, if its signal drops below the sell
    threshold, generate a SELL order.  For top-scoring unheld codes,
    generate BUY orders up to ``max_positions``.
    """

    def __init__(
        self,
        buy_threshold: float = 0.0,
        sell_threshold: float = -0.01,
        top_k: int = 30,
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.top_k = top_k

    def generate(
        self,
        signals: dict[str, float],
        current_positions: dict[str, dict],
        dt: date,
        available_codes: list[str],
        max_positions: int = 50,
    ) -> list[Order]:
        orders: list[Order] = []

        # Sort codes by signal strength
        sorted_signals = sorted(
            ((c, s) for c, s in signals.items() if c in available_codes),
            key=lambda kv: kv[1],
            reverse=True,
        )

        # 1. Sell: held positions whose signal dropped below sell threshold
        held_codes = set(current_positions.keys())
        for code, score in sorted_signals:
            if code in held_codes and score < self.sell_threshold:
                pos = current_positions[code]
                orders.append(
                    Order(
                        code=code,
                        date=dt,
                        direction="sell",
                        quantity=pos.get("qty", 0),
                        signal_score=score,
                        reason=f"signal_drop {score:.4f} < {self.sell_threshold}",
                    )
                )
                held_codes.discard(code)

        # 2. Buy: top-k unheld codes above buy threshold
        available_slots = max_positions - len(held_codes)
        bought = 0
        for code, score in sorted_signals:
            if bought >= available_slots:
                break
            if code not in held_codes and score > self.buy_threshold:
                orders.append(
                    Order(
                        code=code,
                        date=dt,
                        direction="buy",
                        quantity=0.0,  # fill later via portfolio sizing
                        signal_score=score,
                        reason=f"signal_buy {score:.4f}",
                    )
                )
                bought += 1

        return orders


class OrderGenWOInteract(OrderGenerator):
    """Order generation WITHOUT interaction — independent buy/sell.

    Every signal is evaluated independently: positive -> BUY, negative -> SELL.
    Useful for strategies where positions should be re-evaluated from scratch
    each period.
    """

    def __init__(
        self,
        buy_threshold: float = 0.0,
        sell_threshold: float = -0.01,
        top_k: int = 30,
    ):
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.top_k = top_k

    def generate(
        self,
        signals: dict[str, float],
        current_positions: dict[str, dict],
        dt: date,
        available_codes: list[str],
        max_positions: int = 50,
    ) -> list[Order]:
        orders: list[Order] = []

        sorted_signals = sorted(
            ((c, s) for c, s in signals.items() if c in available_codes),
            key=lambda kv: kv[1],
            reverse=True,
        )

        # Buy top-k positive signals
        buy_candidates = [
            (c, s) for c, s in sorted_signals if s > self.buy_threshold
        ][: self.top_k]

        for code, score in buy_candidates[:max_positions]:
            orders.append(
                Order(
                    code=code,
                    date=dt,
                    direction="buy",
                    quantity=0.0,
                    signal_score=score,
                    reason=f"buy {score:.4f}",
                )
            )

        # Sell bottom-k negative signals
        sell_candidates = sorted(
            [(c, s) for c, s in sorted_signals if s < self.sell_threshold],
            key=lambda kv: kv[1],
        )[: self.top_k]

        for code, score in sell_candidates:
            orders.append(
                Order(
                    code=code,
                    date=dt,
                    direction="sell",
                    quantity=0.0,
                    signal_score=score,
                    reason=f"sell {score:.4f}",
                )
            )

        return orders
