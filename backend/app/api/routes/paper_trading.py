from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])

_orders: list[dict] = []
_returns: list[dict] = []
_account: dict = {"balance": 1000000.0, "initial_balance": 1000000.0}

class AccountStatus(BaseModel):
    balance: float
    initial_balance: float


class SettleRequest(BaseModel):
    trade_date: date


@router.post("/settle")
def settle_paper_trading(request: SettleRequest) -> dict:
    result = {"trade_date": request.trade_date.isoformat(), "status": "queued"}
    _returns.append(result)
    return result


@router.get("/orders")
def list_orders() -> list[dict]:
    return _orders


@router.get("/returns")
def list_returns() -> list[dict]:
    return _returns


@router.get("/account")
def get_account() -> AccountStatus:
    return AccountStatus(**_account)


@router.post("/account/reset")
def reset_account() -> AccountStatus:
    _account["balance"] = 1000000.0
    _orders.clear()
    _returns.clear()
    return AccountStatus(**_account)
