from datetime import UTC, datetime

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.paper_trading import PaperOrder, PaperAccount, PaperPosition
from app.schemas.paper_trading import PaperOrderCreate, SettlementResult


def calculate_order_return(order: PaperOrderCreate, close_price: float) -> SettlementResult:
    pnl = (close_price - order.entry_price) * order.quantity
    return_pct = ((close_price - order.entry_price) / order.entry_price) * 100
    return SettlementResult(pnl=round(pnl, 2), return_pct=round(return_pct, 4))


class PaperTradingService:
    def __init__(self, db: Session):
        self.db = db

    def get_account(self) -> PaperAccount:
        account = self.db.scalars(select(PaperAccount).limit(1)).first()
        if not account:
            account = PaperAccount(initial_balance=1000000.0, balance=1000000.0)
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        return account

    def reset_account(self) -> PaperAccount:
        # Instead of deleting, we preserve historical data for LLM analysis.
        # We just set active orders/positions to "archived" and reset balance.
        
        # Archive open/settled orders
        orders = self.db.scalars(select(PaperOrder).where(PaperOrder.status.in_(["open", "settled"]))).all()
        for o in orders:
            o.status = "archived"
            
        # Archive open positions
        positions = self.db.scalars(select(PaperPosition).where(PaperPosition.status == "open")).all()
        for p in positions:
            p.status = "archived"

        account = self.get_account()
        account.balance = account.initial_balance
        
        self.db.commit()
        self.db.refresh(account)
        return account

    def list_orders(self) -> list[PaperOrder]:
        # Fetch non-archived orders, ordered by newest first
        return list(self.db.scalars(
            select(PaperOrder)
            .where(PaperOrder.status != "archived")
            .order_by(PaperOrder.trade_date.desc(), PaperOrder.created_at.desc())
        ).all())

    def create_long_order(self, data: PaperOrderCreate) -> PaperOrder | None:
        account = self.get_account()
        
        cost = data.entry_price * data.quantity
        if account.balance < cost:
            # Insufficient balance
            return None
            
        # Deduct balance
        account.balance -= cost
        
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
        self.db.commit()
        self.db.refresh(order)
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
        self.db.commit()
        self.db.refresh(order)
        return order
