import time
from datetime import date, datetime, timedelta, UTC
import random

from app.services.data.service import MarketDataService
from app.services.strategy.registry import default_strategy_registry
from app.schemas.paper_trading import PaperOrderCreate
from app.schemas.snapshot import StockSnapshotCreate


def execute_strategy_run(task_id: str, strategy_name: str, trade_date: date, parameters: dict):
    from app.db.session import SessionLocal
    from app.services.paper_trading.service import PaperTradingService
    from app.models.strategy import StrategyRun
    from sqlalchemy import select

    registry = default_strategy_registry()
    strategy = registry.get(strategy_name)
    market_data = MarketDataService()

    while True:
        try:
            with SessionLocal() as db:
                run_record = db.get(StrategyRun, task_id)
                if not run_record:
                    print(f"Strategy run {task_id} not found, exiting daemon.")
                    break

                status = run_record.status
                if status == "terminated":
                    print(f"Strategy run {task_id} terminated by user.")
                    break
                elif status == "paused":
                    pass # just sleep and skip execution this cycle
                elif status in ["failed", "completed"]:
                    break # shouldn't happen if it's a daemon, but safety check
                elif status == "running":
                    print(f"Running strategy {strategy_name} for task {task_id}...")
                    # We use today's date for paper trading
                    today = datetime.now().date()
                    
                    all_stocks = market_data.list_stocks()
                    valid_codes = [s.code for s in all_stocks if "ST" not in s.name.upper() and not s.name.startswith("*")]
                    stock_pool = random.sample(valid_codes, min(100, len(valid_codes)))
                    
                    fetch_start = today - timedelta(days=120)
                    matched_stocks = []
                    
                    for code in stock_pool:
                        try:
                            # 1. Preliminary screen using ONLY local cached data
                            bars = market_data.get_daily_bars(code, fetch_start, today, offline_only=True)
                            if not bars:
                                continue
                            signal = strategy.evaluate(code, bars, context=parameters)
                            
                            if signal.matched:
                                # 2. Preliminary matched! Now fetch live data to confirm
                                import time
                                time.sleep(1.5) # Throttle to prevent akshare IP ban
                                full_bars = market_data.get_daily_bars(code, fetch_start, today)
                                if full_bars:
                                    final_signal = strategy.evaluate(code, full_bars, context=parameters)
                                    if final_signal.matched:
                                        matched_stocks.append({"code": code, "latest": full_bars[-1]})
                        except Exception as e:
                            print(f"Error evaluating {code}: {e}")
                            continue

                    paper_service = PaperTradingService(db)

                    # ── Auto-settle previous open orders ─────────────────────────
                    current_orders = paper_service.list_orders()
                    # only settle orders that belong to THIS strategy to prevent interference
                    open_order_codes = list({
                        o.stock_code for o in current_orders 
                        if o.status == "open" and o.strategy_name == strategy_name
                    })

                    if open_order_codes:
                        price_map: dict[str, float] = {}
                        settle_start = today - timedelta(days=10)
                        for code in open_order_codes:
                            try:
                                bars = market_data.get_daily_bars(code, settle_start, today)
                                if bars:
                                    price_map[code] = bars[-1].close
                            except Exception as e:
                                print(f"Failed to fetch settle price for {code}: {e}")

                        settled = paper_service.settle_open_orders(price_map)
                        if settled:
                            settle_dates = {o.trade_date for o in settled}
                            for sd in settle_dates:
                                paper_service.record_daily_return(sd, strategy_name=strategy_name)
                            print(f"Auto-settled {len(settled)} previous open orders.")

                    # ── Open new positions ───────────────────────────────────────
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
                        
                        order_data = PaperOrderCreate(
                            stock_code=match["code"],
                            stock_name=f"样例 {match['code']}",
                            trade_date=today,
                            entry_price=entry_price,
                            quantity=quantity,
                            run_id=task_id
                        )
                        
                        paper_service.create_long_order(order_data, strategy_name=strategy_name)

                    # Update parameters to reflect progress
                    params = run_record.parameters.copy()
                    params["last_matched_count"] = len(matched_stocks)
                    params["last_run_time"] = datetime.now(UTC).isoformat()
                    run_record.parameters = params
                    db.commit()
            
        except Exception as e:
            print(f"Error in strategy daemon {task_id}: {e}")
            try:
                from app.db.session import SessionLocal
                from app.models.strategy import StrategyRun
                with SessionLocal() as db:
                    run_record = db.get(StrategyRun, task_id)
                    if run_record:
                        run_record.status = "failed"
                        run_record.error_message = str(e)
                        db.commit()
            except Exception:
                pass
            break
            
        # Sleep before next iteration. Since this is a demo/simulation, we sleep for 60 seconds
        time.sleep(60)
