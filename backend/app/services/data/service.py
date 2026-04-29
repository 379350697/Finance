from datetime import date

from app.schemas.market import DailyBar, StockInfo, StockQuote
from app.services.data.akshare_provider import AkshareProvider
from app.services.data.cache import ParquetCache
from app.services.data.provider import MarketDataProvider


class MarketDataService:
    def __init__(self, provider: MarketDataProvider | None = None):
        self.provider = provider or AkshareProvider()
        self.cache = ParquetCache(provider=self.provider if isinstance(self.provider, AkshareProvider) else None)

    def list_stocks(self) -> list[StockInfo]:
        return self.provider.list_stocks()

    def get_quote(self, code: str) -> StockQuote:
        return self.provider.get_quote(code)

    def get_daily_bars(self, code: str, start: date, end: date, offline_only: bool = False) -> list[DailyBar]:
        return self.cache.get_bars(code, start, end, offline_only=offline_only)
