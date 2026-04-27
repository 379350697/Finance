from typing import Protocol

from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal


class BaseStrategy(Protocol):
    name: str
    display_name: str

    def evaluate(self, stock_code: str, bars: list[DailyBar]) -> StrategySignal:
        ...


class StrategyEngine:
    def __init__(self, strategies: list[BaseStrategy]):
        self.strategies = strategies

    def evaluate(self, stock_code: str, bars: list[DailyBar]) -> list[StrategySignal]:
        return [strategy.evaluate(stock_code, bars) for strategy in self.strategies]
