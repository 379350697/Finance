from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.paper_trading import PaperOrder
from app.schemas.paper_trading import PaperOrderCreate, SettlementResult


def calculate_order_return(order: PaperOrderCreate, close_price: float) -> SettlementResult:
    pnl = (close_price - order.entry_price) * order.quantity
    return_pct = ((close_price - order.entry_price) / order.entry_price) * 100
    return SettlementResult(pnl=round(pnl, 2), return_pct=round(return_pct, 4))


class PaperTradingService:
    def __init__(self, db: Session):
        self.db = db

    def create_long_order(self, data: PaperOrderCreate) -> PaperOrder:
        order = PaperOrder(
            run_id=data.run_id,
            snapshot_id=data.snapshot_id,
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            trade_date=data.trade_date,
            side="buy",
            status="open",
            entry_price=data.entry_price,
            quantity=data.quantity,
        )
        self.db.add(order)
        self.db.flush()
        return order

    def settle_order(self, order: PaperOrder, close_price: float) -> PaperOrder:
        result = calculate_order_return(
            PaperOrderCreate(
                run_id=order.run_id,
                snapshot_id=order.snapshot_id,
                stock_code=order.stock_code,
                stock_name=order.stock_name,
                trade_date=order.trade_date,
                entry_price=order.entry_price,
                quantity=order.quantity,
            ),
            close_price=close_price,
        )
        order.close_price = close_price
        order.pnl = result.pnl
        order.return_pct = result.return_pct
        order.status = "settled"
        order.settled_at = datetime.now(UTC)
        self.db.flush()
        return order
