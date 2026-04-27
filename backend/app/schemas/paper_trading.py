from datetime import date

from pydantic import BaseModel


class PaperOrderCreate(BaseModel):
    stock_code: str
    stock_name: str
    trade_date: date
    entry_price: float
    quantity: int
    run_id: str | None = None
    snapshot_id: str | None = None


class SettlementResult(BaseModel):
    pnl: float
    return_pct: float
