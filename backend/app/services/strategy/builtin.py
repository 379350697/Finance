from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal
from app.services.strategy.indicators import moving_average, volume_average


class MovingAverageBreakoutStrategy:
    name = "moving_average_breakout"
    display_name = "均线放量突破"

    def evaluate(
        self,
        stock_code: str,
        bars: list[DailyBar],
        context: dict | None = None,
    ) -> StrategySignal:
        if len(bars) < 5:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason="K线数量不足，无法计算 5 日均线",
            )

        closes = [bar.close for bar in bars]
        volumes = [bar.volume or 0 for bar in bars]
        latest = bars[-1]
        ma5 = moving_average(closes, 5)
        volume_ma5 = volume_average(volumes, 5)

        if ma5 is None or volume_ma5 is None or volume_ma5 <= 0:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason="均线或成交量数据不足",
            )

        volume_ratio = (latest.volume or 0) / volume_ma5
        price_strength = ((latest.close - ma5) / ma5) * 100
        matched = latest.close > ma5 and volume_ratio >= 1.5

        return StrategySignal(
            stock_code=stock_code,
            strategy_name=self.name,
            matched=matched,
            reason=(
                f"收盘价突破 5 日均线，量比 {volume_ratio:.2f}"
                if matched
                else "未同时满足均线突破和放量条件"
            ),
            score=round(max(price_strength, 0) * 4 + max(volume_ratio - 1, 0) * 20, 2),
            metrics={
                "close": latest.close,
                "ma5": round(ma5, 4),
                "volume": latest.volume,
                "volume_ma5": round(volume_ma5, 4),
                "volume_ratio": round(volume_ratio, 4),
                "price_strength": round(price_strength, 4),
            },
        )


class TrendReversalStrategy:
    name = "trend_reversal"
    display_name = "趋势反转策略"
    volume_ratio_threshold = 1.5
    large_order_threshold = 5_000_000

    def evaluate(
        self,
        stock_code: str,
        bars: list[DailyBar],
        context: dict | None = None,
    ) -> StrategySignal:
        context = context or {}
        if len(bars) < 63:
            return self._reject(stock_code, "K线数量不足，至少需要 63 个交易日判断 60日均线趋势")

        profit_forecast = context.get("profit_forecast", {})
        is_profit_increase = bool(profit_forecast.get("is_profit_increase"))
        if not is_profit_increase:
            return self._reject(stock_code, "不符合收益预增条件")

        if not _is_three_consecutive_bearish_days(bars[-4:-1]):
            return self._reject(stock_code, "今天前未形成至少日线三连阴")

        closes = [bar.close for bar in bars]
        ma60_today = moving_average(closes, 60)
        ma60_prev = moving_average(closes[:-1], 60)
        if ma60_today is None or ma60_prev is None:
            return self._reject(stock_code, "60日均线数据不足")

        ma60_rising = ma60_today > ma60_prev
        if not ma60_rising:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason="60日均线不是上升趋势",
                metrics={"ma60": round(ma60_today, 4), "ma60_prev": round(ma60_prev, 4)},
            )

        intraday = context.get("intraday", {})
        latest_price = _float_or_none(intraday.get("latest_price"))
        previous_close = _float_or_none(intraday.get("previous_close"))
        volume_ratio = _float_or_none(intraday.get("volume_ratio")) or 0
        large_order_inflow = _float_or_none(intraday.get("large_order_inflow")) or 0

        price_up = latest_price is not None and previous_close is not None and latest_price > previous_close
        volume_trigger = volume_ratio >= self.volume_ratio_threshold
        large_order_trigger = large_order_inflow >= self.large_order_threshold
        intraday_volume_up = price_up and (volume_trigger or large_order_trigger)

        if not intraday_volume_up:
            return StrategySignal(
                stock_code=stock_code,
                strategy_name=self.name,
                matched=False,
                reason="盘中未出现放量上涨或 500 万以上大单流入",
                metrics={
                    "ma60": round(ma60_today, 4),
                    "ma60_prev": round(ma60_prev, 4),
                    "ma60_rising": ma60_rising,
                    "price_up": price_up,
                    "volume_ratio": round(volume_ratio, 4),
                    "large_order_inflow": large_order_inflow,
                    "large_order_trigger": large_order_trigger,
                    "intraday_volume_up": False,
                },
            )

        score = 70 + min(max(volume_ratio - 1, 0) * 10, 15) + (15 if large_order_trigger else 0)
        return StrategySignal(
            stock_code=stock_code,
            strategy_name=self.name,
            matched=True,
            reason="趋势反转策略命中：收益预增、前三日三连阴、盘中放量上涨、60日均线处于上升趋势",
            score=round(score, 2),
            metrics={
                "forecast_type": profit_forecast.get("forecast_type"),
                "ma60": round(ma60_today, 4),
                "ma60_prev": round(ma60_prev, 4),
                "ma60_rising": True,
                "three_bearish_days": True,
                "latest_price": latest_price,
                "previous_close": previous_close,
                "price_up": price_up,
                "volume_ratio": round(volume_ratio, 4),
                "volume_trigger": volume_trigger,
                "large_order_inflow": large_order_inflow,
                "large_order_trigger": large_order_trigger,
                "intraday_volume_up": True,
            },
        )

    def _reject(self, stock_code: str, reason: str) -> StrategySignal:
        return StrategySignal(
            stock_code=stock_code,
            strategy_name=self.name,
            matched=False,
            reason=reason,
        )


def _is_three_consecutive_bearish_days(bars: list[DailyBar]) -> bool:
    return len(bars) >= 3 and all(bar.close < bar.open for bar in bars[-3:])


def _float_or_none(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
