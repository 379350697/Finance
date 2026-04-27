from datetime import date

from app.schemas.paper_trading import PaperOrderCreate
from app.services.paper_trading.service import calculate_order_return


def test_calculate_order_return_for_long_trade():
    order = PaperOrderCreate(
        stock_code="000001",
        stock_name="平安银行",
        trade_date=date(2026, 4, 27),
        entry_price=10,
        quantity=100,
    )

    result = calculate_order_return(order, close_price=11)

    assert result.pnl == 100
    assert result.return_pct == 10
