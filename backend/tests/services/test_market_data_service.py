from datetime import date

from app.schemas.market import StockInfo, StockQuote
from app.services.data.service import MarketDataService


class FakeProvider:
    def list_stocks(self) -> list[StockInfo]:
        return [StockInfo(code="000001", name="测试股票")]

    def get_quote(self, code: str) -> StockQuote:
        return StockQuote(code=code, name="测试股票", price=10.5, change_pct=1.2)

    def get_daily_bars(self, code: str, start: date, end: date):
        return []


def test_market_data_service_returns_quote():
    service = MarketDataService(provider=FakeProvider())

    quote = service.get_quote("000001")

    assert quote.code == "000001"
    assert quote.price == 10.5


def test_market_data_service_lists_all_stocks():
    service = MarketDataService(provider=FakeProvider())

    stocks = service.list_stocks()

    assert stocks[0].code == "000001"
