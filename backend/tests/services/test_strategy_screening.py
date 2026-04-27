from datetime import date, timedelta

from app.schemas.market import DailyBar
from app.services.strategy.screening import StockScreeningInput, StrategyScreeningService


def build_bars(code: str) -> list[DailyBar]:
    bars = [
        DailyBar(
            code=code,
            trade_date=date(2026, 1, 1) + timedelta(days=i),
            open=10 + i * 0.02,
            high=10.2 + i * 0.02,
            low=9.9 + i * 0.02,
            close=10 + i * 0.02,
            volume=1000,
        )
        for i in range(64)
    ]
    bars[-4] = bars[-4].model_copy(update={"open": 12.2, "close": 11.7})
    bars[-3] = bars[-3].model_copy(update={"open": 11.8, "close": 11.2})
    bars[-2] = bars[-2].model_copy(update={"open": 11.3, "close": 10.9})
    return bars


def test_screening_service_filters_all_stocks_for_trend_reversal():
    service = StrategyScreeningService()
    inputs = [
        StockScreeningInput(
            code="000001",
            name="平安银行",
            bars=build_bars("000001"),
            profit_forecast={"is_profit_increase": True, "forecast_type": "预增"},
            intraday={
                "latest_price": 12.6,
                "previous_close": 10.9,
                "volume_ratio": 1.8,
                "large_order_inflow": 0,
            },
        ),
        StockScreeningInput(
            code="000002",
            name="万科A",
            bars=build_bars("000002"),
            profit_forecast={"is_profit_increase": False, "forecast_type": "预减"},
            intraday={
                "latest_price": 12.6,
                "previous_close": 10.9,
                "volume_ratio": 1.8,
                "large_order_inflow": 0,
            },
        ),
    ]

    results = service.screen("trend_reversal", inputs)

    assert [result.stock_code for result in results] == ["000001"]
    assert results[0].stock_name == "平安银行"
