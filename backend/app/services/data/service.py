from datetime import date

from app.schemas.market import DailyBar, StockQuote
from app.services.data.akshare_provider import AkshareProvider
from app.services.data.provider import MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider | None = None):
        self.provider = provider or AkshareProvider()

    def get_quote(self, code: str) -> StockQuote:
        return self.provider.get_quote(code)

    def get_daily_bars(self, code: str, start: date, end: date) -> list[DailyBar]:
        return self.provider.get_daily_bars(code, start, end)
