from app.services.strategy.builtin import MovingAverageBreakoutStrategy, TrendReversalStrategy, TestFastExecutionStrategy
from app.services.strategy.engine import BaseStrategy


class StrategyRegistry:
    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> None:
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> BaseStrategy:
        return self._strategies[name]

    def list(self) -> list[BaseStrategy]:
        return list(self._strategies.values())


def default_strategy_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(MovingAverageBreakoutStrategy())
    registry.register(TrendReversalStrategy())
    registry.register(TestFastExecutionStrategy())
    return registry
