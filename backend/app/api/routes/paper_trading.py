from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/paper-trading", tags=["paper-trading"])

_orders: list[dict] = []
_returns: list[dict] = []


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
