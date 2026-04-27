from datetime import date, timedelta

from app.schemas.market import DailyBar
from app.schemas.paper_trading import PaperOrderCreate
from app.schemas.snapshot import StockSnapshotCreate
from app.services.llm.report_service import build_fallback_daily_report
from app.services.paper_trading.service import calculate_order_return
from app.services.strategy.builtin import MovingAverageBreakoutStrategy


def demo_bars() -> list[DailyBar]:
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
    bars[-1] = bars[-1].model_copy(
        update={
            "trade_date": date(2026, 4, 27),
            "close": 14.0,
            "volume": 3000,
        }
    )
    return bars


def run_closed_loop_demo() -> dict:
    bars = demo_bars()
    signal = MovingAverageBreakoutStrategy().evaluate("000001", bars)
    latest = bars[-1]

    snapshot = StockSnapshotCreate(
        stock_code="000001",
        stock_name="平安银行",
        trade_date=latest.trade_date,
        quote_data={
            "price": latest.close,
            "volume": latest.volume,
        },
        indicator_data=signal.metrics,
        strategy_data={
            "strategy_name": signal.strategy_name,
            "matched": signal.matched,
            "reason": signal.reason,
            "score": signal.score,
        },
        raw_data={"bars": [bar.model_dump(mode="json") for bar in bars[-5:]]},
    )

    order = PaperOrderCreate(
        stock_code=snapshot.stock_code,
        stock_name=snapshot.stock_name,
        trade_date=snapshot.trade_date,
        entry_price=10,
        quantity=100,
    )
    settlement = calculate_order_return(order, close_price=11)

    report = build_fallback_daily_report(
        trade_date=snapshot.trade_date.isoformat(),
        candidates_count=1 if signal.matched else 0,
        orders_count=1,
        total_return_pct=settlement.return_pct,
    )

    return {
        "bars": bars,
        "signal": signal,
        "snapshot": snapshot,
        "order": order,
        "settlement": settlement,
        "report": report,
    }
