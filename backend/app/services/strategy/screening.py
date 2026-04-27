from pydantic import BaseModel, Field

from app.schemas.market import DailyBar
from app.schemas.strategy import StrategySignal
from app.services.strategy.registry import StrategyRegistry, default_strategy_registry


class StockScreeningInput(BaseModel):
    code: str
    name: str
    bars: list[DailyBar]
    profit_forecast: dict = Field(default_factory=dict)
    intraday: dict = Field(default_factory=dict)


class StrategyScreeningService:
    def __init__(self, registry: StrategyRegistry | None = None):
        self.registry = registry or default_strategy_registry()

    def screen(self, strategy_name: str, stocks: list[StockScreeningInput]) -> list[StrategySignal]:
        strategy = self.registry.get(strategy_name)
        matched: list[StrategySignal] = []

        for stock in stocks:
            signal = strategy.evaluate(
                stock.code,
                stock.bars,
                context={
                    "profit_forecast": stock.profit_forecast,
                    "intraday": stock.intraday,
                },
            )
            if signal.matched:
                matched.append(signal.model_copy(update={"stock_name": stock.name}))

        return matched
