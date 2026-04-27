from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal
from app.services.strategy.indicators import moving_average, volume_average


class MovingAverageBreakoutStrategy:
    name = "moving_average_breakout"
    display_name = "均线放量突破"

    def evaluate(self, stock_code: str, bars: list[DailyBar]) -> StrategySignal:
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
