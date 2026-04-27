from datetime import date
from typing import Protocol

from app.schemas.market import DailyBar, StockQuote


class MarketDataError(RuntimeError):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        super().__init__(f"{provider}: {message}")


class MarketDataProvider(Protocol):
    def get_quote(self, code: str) -> StockQuote:
        ...

    def get_daily_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        ...
