from typing import Protocol

from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal


class BaseStrategy(Protocol):
    name: str
    display_name: str

    def evaluate(
        self,
        stock_code: str,
        bars: list[DailyBar],
        context: dict | None = None,
    ) -> StrategySignal:
        ...


class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy]):
        self.strategies = strategies

    def evaluate(
        self,
        stock_code: str,
        bars: list[DailyBar],
        context: dict | None = None,
    ) -> list[StrategySignal]:
        return [strategy.evaluate(stock_code, bars, context=context) for strategy in self.strategies]
