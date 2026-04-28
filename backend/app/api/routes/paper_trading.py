from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.paper_trading import SettlementResult
from app.services.paper_trading.service import PaperTradingService

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])


@router.post("/settle")
def settle_paper_trading(trade_date: date, db: Session = Depends(get_db)) -> dict:
    # Future placeholder for settlement logic
    result = {"trade_date": trade_date.isoformat(), "status": "queued"}
    return result


@router.get("/orders")
def list_orders(db: Session = Depends(get_db)) -> list[dict]:
    service = PaperTradingService(db)
    orders = service.list_orders()
    return [
        {
            "id": o.id,
            "stock_code": o.stock_code,
            "stock_name": o.stock_name,
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


@router.get("/returns")
def list_returns() -> list[dict]:
    # Placeholder for daily returns
    return []


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
