import asyncio
from datetime import date, timedelta
import random

from app.services.data.service import MarketDataService
from app.services.strategy.registry import default_strategy_registry
from app.schemas.paper_trading import PaperOrderCreate
from app.schemas.snapshot import StockSnapshotCreate


def execute_strategy_run(task_id: str, strategy_name: str, trade_date: date, parameters: dict):
    from app.api.routes.strategies import _strategy_runs
    from app.db.session import SessionLocal
    from app.services.paper_trading.service import PaperTradingService

    try:
        registry = default_strategy_registry()
        strategy = registry.get(strategy_name)
        market_data = MarketDataService()

        # Get all stocks, filter ST, and take a random sample of 100 to keep it reasonably fast
        all_stocks = market_data.list_stocks()
        valid_codes = [
            s.code for s in all_stocks 
            if "ST" not in s.name.upper() and not s.name.startswith("*")
        ]
        stock_pool = random.sample(valid_codes, min(100, len(valid_codes)))
        
        fetch_start = trade_date - timedelta(days=120)
        matched_stocks = []

        for code in stock_pool:
            try:
                bars = market_data.get_daily_bars(code, fetch_start, trade_date)
                if not bars:
                    continue
                
                # Evaluate strategy
                signal = strategy.evaluate(code, bars, context=parameters)
                
                if signal.matched:
                    latest = bars[-1]
                    matched_stocks.append({
                        "code": code,
                        "signal": signal,
                        "latest": latest,
                        "bars": bars[-5:] # keep last 5 for context
                    })
            except Exception as e:
                print(f"Error evaluating {code}: {e}")
                continue

        # Real DB session for PaperTradingService
        with SessionLocal() as db:
            paper_service = PaperTradingService(db)
            account = paper_service.get_account()

            for match in matched_stocks:
                entry_price = match["latest"].close
                if entry_price <= 0:
                    continue
                    
                max_spend = min(100000.0, account.balance)
                # Round down to nearest lot of 100
                quantity = int((max_spend / entry_price) // 100) * 100
                
                if quantity < 100:
                    print(f"Skipping {match['code']} due to insufficient balance.")
                    continue
                
                # Create the order via the service
                order_data = PaperOrderCreate(
                    stock_code=match["code"],
                    stock_name=f"样例 {match['code']}",
                    trade_date=trade_date,
                    entry_price=entry_price,
                    quantity=quantity,
                    run_id=task_id
                )
                
                # This automatically deducts balance inside the service
                paper_service.create_long_order(order_data)

        _strategy_runs[task_id]["status"] = "completed"
        _strategy_runs[task_id]["matched_count"] = len(matched_stocks)
        
    except Exception as e:
        print(f"Strategy run failed: {e}")
        _strategy_runs[task_id]["status"] = "failed"
