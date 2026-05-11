"""
ExchangeSimulator: simulates A-share stock exchange rules for backtesting.

Covers:
- Price limits (main board 10%, STAR/ChiNext 20%, ST stocks 5%)
- T+1 settlement (must hold at least 1 calendar day)
- Trading suspension detection (volume=0 or high==low flat line)
- Limit-up / limit-down fill checks
"""

from __future__ import annotations

from datetime import date

from app.schemas.market import DailyBar

# Board classification helpers -------------------------------------------------
_STAR_PREFIXES = ("688",)
_CHINEXT_PREFIXES = ("300", "301")
_ST_PREFIX = "ST"


def _is_star(code: str) -> bool:
    return code.startswith(_STAR_PREFIXES)


def _is_chinext(code: str) -> bool:
    return code.startswith(_CHINEXT_PREFIXES)


def _is_st(code: str) -> bool:
    return _ST_PREFIX in code


def _limit_rate(code: str) -> float:
    """Return the daily price-limit rate for *code*."""
    if _is_st(code):
        return 0.05
    if _is_star(code) or _is_chinext(code):
        return 0.20
    return 0.10


# ---------------------------------------------------------------------------


class ExchangeSimulator:
    """Simulates A-share exchange-level constraints during backtesting.

    Parameters
    ----------
    bars_dict : dict[str, list[DailyBar]]
        {code: [DailyBar sorted by trade_date]}
    """

    def __init__(self, bars_dict: dict[str, list[DailyBar]]) -> None:
        self._bars_dict = bars_dict
        # Build quick lookups:  {code: {trade_date: bar}}
        self._bar_map: dict[str, dict[date, DailyBar]] = {}
        for code, bars in bars_dict.items():
            self._bar_map[code] = {}
            for bar in bars:
                self._bar_map[code][bar.trade_date] = bar

        # Pre-compute previous close mapping for limit price calculation.
        self._prev_close: dict[str, dict[date, float]] = {}
        for code, bars in bars_dict.items():
            sorted_bars = sorted(bars, key=lambda b: b.trade_date)
            self._prev_close[code] = {}
            prev_close: float | None = None
            for bar in sorted_bars:
                if prev_close is not None:
                    self._prev_close[code][bar.trade_date] = prev_close
                prev_close = bar.close

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def can_trade(self, code: str, dt: date) -> bool:
        """Return True if *code* is not suspended on *dt*.

        A stock is considered suspended if:
        - There is no bar for that date, or
        - Volume is 0 or None, or
        - The bar is a flat line (high == low) indicating no trading.
        """
        bar = self._bar_map.get(code, {}).get(dt)
        if bar is None:
            return False
        vol = bar.volume
        if vol is None or vol == 0:
            return False
        if bar.high == bar.low:
            return False
        return True

    def is_limit_up(self, code: str, dt: date) -> bool:
        """Return True if the stock hit its daily price ceiling."""
        bar = self._bar_map.get(code, {}).get(dt)
        if bar is None:
            return False
        limit = self.limit_up_price(code, dt)
        return bar.close >= limit and bar.low >= limit and bar.close > 0

    def is_limit_down(self, code: str, dt: date) -> bool:
        """Return True if the stock hit its daily price floor."""
        bar = self._bar_map.get(code, {}).get(dt)
        if bar is None:
            return False
        limit = self.limit_down_price(code, dt)
        return bar.close <= limit and bar.high <= limit and bar.close > 0

    def limit_up_price(self, code: str, dt: date) -> float:
        """Calculate the limit-up price for *code* on *dt*."""
        prev = self._get_prev_close(code, dt)
        rate = _limit_rate(code)
        return round(prev * (1 + rate), 2)

    def limit_down_price(self, code: str, dt: date) -> float:
        """Calculate the limit-down price for *code* on *dt*."""
        prev = self._get_prev_close(code, dt)
        rate = _limit_rate(code)
        return round(prev * (1 - rate), 2)

    def get_fill_price(
        self,
        code: str,
        dt: date,
        side: str,
        desired_price: float,
    ) -> float | None:
        """Check whether a trade at *desired_price* can fill on *dt*.

        Returns the actual fill price (capped at limit) or None if the
        stock is suspended or the desired price cannot be met due to
        limit constraints.

        Parameters
        ----------
        side : str
            "buy" or "sell".
        """
        if not self.can_trade(code, dt):
            return None

        bar = self._bar_map[code][dt]
        limit_up = self.limit_up_price(code, dt)
        limit_down = self.limit_down_price(code, dt)

        if side == "buy":
            if self.is_limit_up(code, dt):
                # Cannot buy at limit-up — no sellers at that price.
                return None
            # Fill at whichever is lower: desired or limit (can't exceed limit-up)
            return min(desired_price, limit_up)
        else:  # sell
            if self.is_limit_down(code, dt):
                # Cannot sell at limit-down — no buyers.
                return None
            # Fill at whichever is higher: desired or limit (can't go below limit-down)
            return max(desired_price, limit_down)

    def is_t1_eligible(self, code: str, entry_date: date, sell_date: date) -> bool:
        """Check T+1: sell_date must be strictly after entry_date.

        In A-shares, you cannot sell on the same day you buy.
        The sell date must be at least one calendar day later.
        """
        return sell_date > entry_date

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_prev_close(self, code: str, dt: date) -> float | None:
        """Return the previous trading day's close for *code* relative to *dt*."""
        return self._prev_close.get(code, {}).get(dt, None)
