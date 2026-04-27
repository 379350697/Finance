from datetime import date, timedelta

from app.schemas.market import DailyBar
from app.services.strategy.builtin import MovingAverageBreakoutStrategy, TrendReversalStrategy
from app.services.strategy.registry import default_strategy_registry


def test_moving_average_breakout_selects_candidate():
    bars = [
        DailyBar(
            code="000001",
            trade_date=date(2026, 4, 1) + timedelta(days=i),
            open=10 + i * 0.1,
            high=10.5 + i * 0.1,
            low=9.8 + i * 0.1,
            close=10 + i * 0.1,
            volume=1000 + i * 10,
        )
        for i in range(20)
    ]
    bars[-1] = bars[-1].model_copy(update={"close": 14.0, "volume": 3000})

    result = MovingAverageBreakoutStrategy().evaluate("000001", bars)

    assert result.matched is True
    assert "突破" in result.reason


def build_trend_reversal_bars() -> list[DailyBar]:
    bars = [
        DailyBar(
            code="000001",
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


def test_trend_reversal_selects_intraday_volume_reversal_with_rising_ma60():
    result = TrendReversalStrategy().evaluate(
        "000001",
        build_trend_reversal_bars(),
        context={
            "profit_forecast": {"is_profit_increase": True, "forecast_type": "预增"},
            "intraday": {
                "latest_price": 12.6,
                "previous_close": 10.9,
                "volume_ratio": 1.8,
                "large_order_inflow": 0,
            },
        },
    )

    assert result.matched is True
    assert result.strategy_name == "trend_reversal"
    assert "趋势反转" in result.reason
    assert result.metrics["ma60_rising"] is True
    assert result.metrics["intraday_volume_up"] is True


def test_trend_reversal_accepts_large_order_inflow_as_volume_up():
    result = TrendReversalStrategy().evaluate(
        "000001",
        build_trend_reversal_bars(),
        context={
            "profit_forecast": {"is_profit_increase": True, "forecast_type": "预增"},
            "intraday": {
                "latest_price": 11.3,
                "previous_close": 10.9,
                "volume_ratio": 1.0,
                "large_order_inflow": 5_000_000,
            },
        },
    )

    assert result.matched is True
    assert result.metrics["large_order_trigger"] is True


def test_trend_reversal_requires_rising_ma60():
    bars = build_trend_reversal_bars()
    falling_bars = [
        bar.model_copy(update={"open": 20 - index * 0.05, "close": 20 - index * 0.05})
        for index, bar in enumerate(bars)
    ]
    falling_bars[-4] = falling_bars[-4].model_copy(update={"open": 17.2, "close": 16.9})
    falling_bars[-3] = falling_bars[-3].model_copy(update={"open": 17.0, "close": 16.6})
    falling_bars[-2] = falling_bars[-2].model_copy(update={"open": 16.8, "close": 16.4})

    result = TrendReversalStrategy().evaluate(
        "000001",
        falling_bars,
        context={
            "profit_forecast": {"is_profit_increase": True, "forecast_type": "预增"},
            "intraday": {
                "latest_price": 17.2,
                "previous_close": 16.4,
                "volume_ratio": 2.0,
                "large_order_inflow": 0,
            },
        },
    )

    assert result.matched is False
    assert "60日均线" in result.reason


def test_trend_reversal_requires_profit_increase():
    result = TrendReversalStrategy().evaluate(
        "000001",
        build_trend_reversal_bars(),
        context={
            "profit_forecast": {"is_profit_increase": False, "forecast_type": "预减"},
            "intraday": {
                "latest_price": 12.6,
                "previous_close": 10.9,
                "volume_ratio": 1.8,
                "large_order_inflow": 0,
            },
        },
    )

    assert result.matched is False
    assert "收益预增" in result.reason


def test_default_registry_contains_trend_reversal_strategy():
    registry = default_strategy_registry()

    strategy = registry.get("trend_reversal")

    assert strategy.display_name == "趋势反转策略"
