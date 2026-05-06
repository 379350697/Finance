import time
from datetime import date, datetime, timedelta, UTC
import random

from app.services.data.service import MarketDataService
from app.services.strategy.registry import default_strategy_registry
from app.schemas.paper_trading import PaperOrderCreate
from app.schemas.snapshot import StockSnapshotCreate

# Per-session minute bar cache — auto-clears on date change
_today_minute: dict[str, list] = {}
_today_minute_date: date | None = None


def _ensure_minute_bars(market_data: MarketDataService, code: str) -> list:
    global _today_minute, _today_minute_date
    today = date.today()
    if _today_minute_date != today:
        _today_minute = {}
        _today_minute_date = today
    if code not in _today_minute:
        try:
            _today_minute[code] = market_data.get_minute_bars(code, today, today)
        except Exception:
            _today_minute[code] = []
    return _today_minute[code]


def _get_current_price(market_data: MarketDataService, code: str, fallback: float) -> float:
    """Three-tier fallback: minute bars → real-time quote → daily close."""
    from app.core.config import settings

    bars = _ensure_minute_bars(market_data, code)
    if bars:
        return bars[-1].close * (1 + abs(random.gauss(0, settings.slippage_std)))

    try:
        quote = market_data.get_quote(code)
        if quote and quote.price > 0:
            return quote.price * (1 + abs(random.gauss(0, settings.slippage_std)))
    except Exception:
        pass

    return fallback


def _check_intraday_stop(pos, minute_bars: list, stop_loss_pct: float, take_profit_pct: float):
    """Scan intraday minute bars for stop-loss / take-profit triggers."""
    avg = pos.average_price
    for bar in minute_bars:
        low_change = (bar.low - avg) / avg
        high_change = (bar.high - avg) / avg
        if low_change <= stop_loss_pct:
            return True, bar.low
        if high_change >= take_profit_pct:
            return True, bar.high
    return False, None


def execute_strategy_run(task_id: str, strategy_name: str, trade_date: date, parameters: dict):
    from app.db.session import SessionLocal
    from app.services.paper_trading.service import PaperTradingService
    from app.models.strategy import StrategyRun
    from app.core.config import settings
    from sqlalchemy import select
    import random

    registry = default_strategy_registry()
    strategy = registry.get(strategy_name)
    market_data = MarketDataService()

    while True:
        try:
            # 1. Briefly open session to check status
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
                                    matched_stocks.append({"code": code, "latest": full_bars[-1], "bars": full_bars})
                    except Exception as e:
                        print(f"Error evaluating {code}: {e}")
                        continue

                if status == "running":
                    with SessionLocal() as db:
                        paper_service = PaperTradingService(db)

                        # ── Stop-loss / take-profit scan (minute-level) ──────────
                        open_positions = paper_service.list_positions()
                        stop_price_map: dict[str, float] = {}
                        for pos in open_positions:
                            if pos.strategy_name != strategy_name:
                                continue
                            try:
                                minute_bars = _ensure_minute_bars(market_data, pos.stock_code)
                                triggered, trigger_price = _check_intraday_stop(
                                    pos, minute_bars, settings.stop_loss_pct, settings.take_profit_pct
                                )
                                if triggered and trigger_price:
                                    stop_price_map[pos.stock_code] = trigger_price
                            except Exception:
                                continue
                        if stop_price_map:
                            paper_service.settle_open_orders(stop_price_map)
                            print(f"Stop-loss/take-profit settled: {stop_price_map}")

                        # ── Auto-settle previous open orders ─────────────────────────
                        current_orders = paper_service.list_orders()
                        # only settle orders that belong to THIS strategy to prevent interference
                        open_orders_list = [
                            o for o in current_orders 
                            if o.status == "open" and o.strategy_name == strategy_name
                        ]

                        if open_orders_list:
                            price_map: dict[str, float] = {}
                            settle_start = today - timedelta(days=10)
                            for order in open_orders_list:
                                code = order.stock_code
                                try:
                                    import time
                                    time.sleep(1.5)
                                    bars = market_data.get_daily_bars(code, settle_start, today)
                                    if bars:
                                        latest_price = bars[-1].close
                                        if strategy_name == "test_fast_execution":
                                            # For testing the closed loop, we want to guarantee it sells quickly.
                                            # Normally we'd wait for 1% change: abs(...) >= 0.01
                                            # Since local cached daily bars might not change intraday, we use 0.0 to guarantee a sell on next tick
                                            change = abs((latest_price - order.entry_price) / order.entry_price)
                                            if change >= 0.0:
                                                price_map[code] = latest_price
                                        else:
                                            price_map[code] = latest_price
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
                            entry_price = _get_current_price(market_data, match["code"], match["latest"].close)
                            if entry_price <= 0:
                                continue

                            # Price limit check
                            full_bars = match.get("bars", [])
                            if len(full_bars) >= 2:
                                pre_close = full_bars[-2].close
                                limit_up = pre_close * 1.10
                                if entry_price >= limit_up * 0.995:
                                    continue  # near limit-up, can't buy

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
                        run_record = db.get(StrategyRun, task_id)
                        if run_record:
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
