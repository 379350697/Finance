from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.paper_trading import SettlementResult
from app.services.paper_trading.service import PaperTradingService
from app.services.data.service import MarketDataService

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.post("/settle")
def settle_paper_trading(trade_date: date, db: Session = Depends(get_db)) -> dict:
    """Settle all open orders using latest close prices from the market data service."""
    service = PaperTradingService(db)
    open_orders = service.list_orders()
    open_codes = list({o.stock_code for o in open_orders if o.status == "open"})

    if not open_codes:
        return {"trade_date": trade_date.isoformat(), "settled_count": 0, "status": "no_open_orders"}

    # Fetch latest close prices
    market = MarketDataService()
    price_map: dict[str, float] = {}
    fetch_start = trade_date - timedelta(days=10)
    for code in open_codes:
        try:
            bars = market.get_daily_bars(code, fetch_start, trade_date)
            if bars:
                price_map[code] = bars[-1].close
        except Exception as e:
            print(f"Failed to fetch price for {code}: {e}")

    settled = service.settle_open_orders(price_map)

    # Record daily return
    if settled:
        service.record_daily_return(trade_date)

    return {
        "trade_date": trade_date.isoformat(),
        "settled_count": len(settled),
        "status": "completed",
    }


@router.get("/orders")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    service = PaperTradingService(db)
    orders = service.list_orders()
    return [
        {
            "id": o.id,
            "stock_code": o.stock_code,
            "stock_name": o.stock_name,
            "strategy_name": o.strategy_name,
            "trade_date": o.trade_date.isoformat(),
            "entry_price": o.entry_price,
            "close_price": o.close_price,
            "quantity": o.quantity,
            "pnl": o.pnl,
            "return_pct": o.return_pct,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/positions")
def list_positions(db: Session = Depends(get_db)) -> list[dict]:
    """Return all currently open positions in the active session."""
    service = PaperTradingService(db)
    positions = service.list_positions()
    return [
        {
            "id": p.id,
            "stock_code": p.stock_code,
            "stock_name": p.stock_name,
            "quantity": p.quantity,
            "average_price": p.average_price,
            "market_value": p.market_value,
            "pnl": p.pnl,
            "return_pct": p.return_pct,
            "status": p.status,
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
        }
        for p in positions
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)) -> dict:
    """Return aggregate statistics for the active session."""
    service = PaperTradingService(db)
    return service.get_stats()


@router.get("/net-value")
def get_net_value(db: Session = Depends(get_db)) -> list[dict]:
    """Return daily net-value time series for chart rendering."""
    service = PaperTradingService(db)
    return service.get_net_value_series()


@router.get("/returns")
def list_returns(db: Session = Depends(get_db)) -> list[dict]:
    """Return aggregated daily return records for the active session."""
    from app.models.paper_trading import PaperDailyReturn
    from sqlalchemy import select

    service = PaperTradingService(db)
    session = service.get_active_session()

    results = db.scalars(
        select(PaperDailyReturn)
        .where(
            PaperDailyReturn.session_id == session.id,
            PaperDailyReturn.status == "active",
        )
        .order_by(PaperDailyReturn.trade_date.desc())
    ).all()
    return [
        {
            "trade_date": r.trade_date.isoformat(),
            "total_orders": r.total_orders,
            "win_rate": r.win_rate,
            "total_pnl": r.total_pnl,
            "return_pct": r.return_pct,
            "strategy_name": r.strategy_name,
        }
        for r in results
    ]


@router.get("/account")
def get_account(db: Session = Depends(get_db)) -> dict:
    service = PaperTradingService(db)
    account = service.get_account()
    return {
        "balance": account.balance,
        "initial_balance": account.initial_balance
    }


@router.post("/account/reset")
def reset_account(db: Session = Depends(get_db)) -> dict:
    service = PaperTradingService(db)
    account = service.reset_account()
    return {
        "balance": account.balance,
        "initial_balance": account.initial_balance
    }


# ── History / LLM report endpoints ──────────────────────────────────────


@router.get("/sessions")
def list_sessions(
    include_active: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List all simulation sessions (reset cycles) for LLM report analysis."""
    service = PaperTradingService(db)
    sessions = service.list_sessions(include_active=include_active)
    return [
        {
            "id": s.id,
            "label": s.label,
            "status": s.status,
            "initial_balance": s.initial_balance,
            "final_balance": s.final_balance,
            "total_pnl": s.total_pnl,
            "total_trades": s.total_trades,
            "win_rate": s.win_rate,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Return full detail of a session — orders grouped by date and strategy.
    
    Provides the rich sample data LLM needs for daily/monthly report generation.
    """
    service = PaperTradingService(db)
    return service.get_session_detail(session_id)


@router.get("/history")
def get_history_for_report(
    period_start: date | None = Query(None),
    period_end: date | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregate data across ALL sessions for LLM monthly/weekly reports.
    
    Returns cross-session statistics comparing strategy performance over time.
    """
    service = PaperTradingService(db)
    return service.get_all_history_for_report(
        period_start=period_start,
        period_end=period_end,
    )
