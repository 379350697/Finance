from datetime import date, timedelta

from app.schemas.market import DailyBar
from app.services.strategy.builtin import MovingAverageBreakoutStrategy


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
