from datetime import date, timedelta

from app.schemas.backtest import BacktestRequest, BacktestStockBars
from app.schemas.market import DailyBar
from app.services.backtest.service import BacktestService
from tests.services.test_strategy_engine import build_trend_reversal_bars


def make_breakout_bars(code: str) -> list[DailyBar]:
    bars: list[DailyBar] = []
    start = date(2026, 1, 1)
    for index in range(8):
        close = 10 + index * 0.1
        bars.append(
            DailyBar(
                code=code,
                trade_date=start + timedelta(days=index),
                open=close - 0.1,
                high=close + 0.2,
                low=close - 0.2,
                close=close,
                volume=1000,
            )
        )

    bars[5] = bars[5].model_copy(update={"close": 13.0, "volume": 3000})
    bars[6] = bars[6].model_copy(update={"close": 14.0, "volume": 1100})
    return bars


def make_losing_breakout_bars(code: str) -> list[DailyBar]:
    bars = [
        DailyBar(
            code=code,
            trade_date=date(2026, 1, 1) + timedelta(days=index),
            open=10 + index * 0.05,
            high=10.2 + index * 0.05,
            low=9.8 + index * 0.05,
            close=10 + index * 0.05,
            volume=1000,
        )
        for index in range(8)
    ]
    bars[6] = bars[6].model_copy(update={"close": 13.0, "volume": 3000})
    bars[7] = bars[7].model_copy(update={"close": 12.0, "volume": 1100})
    return bars


def test_backtest_service_returns_trades_daily_returns_and_metrics():
    request = BacktestRequest(
        strategy_name="moving_average_breakout",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        stock_pool=["000001"],
        stocks=[
            BacktestStockBars(
                code="000001",
                name="Ping An Bank",
                bars=make_breakout_bars("000001"),
            )
        ],
    )

    result = BacktestService().run(request)

    assert result.strategy_name == "moving_average_breakout"
    assert len(result.trades) == 1
    assert result.trades[0].stock_code == "000001"
    assert result.trades[0].entry_date == date(2026, 1, 6)
    assert result.trades[0].exit_date == date(2026, 1, 7)
    assert result.trades[0].return_pct == 7.69
    assert result.daily_returns[0].trade_date == date(2026, 1, 7)
    assert result.total_return_pct == 0.77
    assert result.win_rate == 1.0
    assert result.max_drawdown_pct == 0


def test_backtest_service_filters_requested_stock_pool():
    request = BacktestRequest(
        strategy_name="moving_average_breakout",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        stock_pool=["000001"],
        stocks=[
            BacktestStockBars(code="000001", name="A", bars=make_breakout_bars("000001")),
            BacktestStockBars(code="000002", name="B", bars=make_breakout_bars("000002")),
        ],
    )

    result = BacktestService().run(request)

    assert {trade.stock_code for trade in result.trades} == {"000001"}


def test_backtest_service_calculates_max_drawdown_from_equity_curve():
    request = BacktestRequest(
        strategy_name="moving_average_breakout",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 8),
        stock_pool=["000001", "000002"],
        stocks=[
            BacktestStockBars(code="000001", name="Winner", bars=make_breakout_bars("000001")),
            BacktestStockBars(code="000002", name="Loser", bars=make_losing_breakout_bars("000002")),
        ],
    )

    result = BacktestService().run(request)

    assert result.trade_count == 2
    assert result.win_rate == 0.5
    assert result.max_drawdown_pct == 0.77


def test_backtest_service_runs_trend_reversal_with_daily_context():
    bars = build_trend_reversal_bars()
    bars[-1] = bars[-1].model_copy(update={"close": 12.6, "volume": 3000})
    request = BacktestRequest(
        strategy_name="trend_reversal",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
        stock_pool=["000001"],
        strategy_params={"profit_forecast": {"is_profit_increase": True, "forecast_type": "预增"}},
        stocks=[
            BacktestStockBars(
                code="000001",
                name="Ping An Bank",
                bars=bars
                + [
                    DailyBar(
                        code="000001",
                        trade_date=date(2026, 3, 6),
                        open=12.6,
                        high=13.2,
                        low=12.5,
                        close=13.1,
                        volume=1100,
                    )
                ],
            )
        ],
    )

    result = BacktestService().run(request)

    assert result.strategy_name == "trend_reversal"
    assert result.trade_count == 1
    assert result.trades[0].stock_code == "000001"
