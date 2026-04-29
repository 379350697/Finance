from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.models.paper_trading import (
    PaperAccount,
    PaperDailyReturn,
    PaperOrder,
    PaperPosition,
    PaperSession,
)
from app.schemas.paper_trading import PaperOrderCreate, SettlementResult


def calculate_order_return(order: PaperOrderCreate, close_price: float) -> SettlementResult:
    pnl = (close_price - order.entry_price) * order.quantity
    return_pct = ((close_price - order.entry_price) / order.entry_price) * 100
    return SettlementResult(pnl=round(pnl, 2), return_pct=round(return_pct, 4))


class PaperTradingService:
    def __init__(self, db: Session):
        self.db = db

    # ── Account & Session ────────────────────────────────────────────────

    def get_account(self) -> PaperAccount:
        account = self.db.scalars(select(PaperAccount).limit(1)).first()
        if not account:
            session = self._create_session()
            account = PaperAccount(
                initial_balance=1000000.0,
                balance=1000000.0,
                active_session_id=session.id,
            )
            self.db.add(account)
            self.db.commit()
            self.db.refresh(account)
        return account

    def get_active_session(self) -> PaperSession:
        """Return the current active session, creating one if none exists."""
        account = self.get_account()
        if account.active_session_id:
            session = self.db.get(PaperSession, account.active_session_id)
            if session and session.status == "active":
                return session
        # Create a fresh session
        session = self._create_session()
        account.active_session_id = session.id
        self.db.commit()
        return session

    def _create_session(self) -> PaperSession:
        now = datetime.now(UTC)
        session = PaperSession(
            initial_balance=1000000.0,
            status="active",
            started_at=now,
            label=f"模拟周期 {now.strftime('%Y-%m-%d %H:%M')}",
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def reset_account(self) -> PaperAccount:
        """Archive the current session with a summary snapshot, then start a new one."""
        account = self.get_account()
        now = datetime.now(UTC)

        # ── Finalize current session ─────────────────────────────────────
        old_session_id = account.active_session_id
        if old_session_id:
            old_session = self.db.get(PaperSession, old_session_id)
            if old_session and old_session.status == "active":
                # Compute session summary before archiving
                session_orders = list(self.db.scalars(
                    select(PaperOrder).where(
                        PaperOrder.session_id == old_session_id,
                        PaperOrder.status == "settled",
                    )
                ).all())
                total_pnl = sum(o.pnl or 0 for o in session_orders)
                total_trades = len(session_orders)
                winners = sum(1 for o in session_orders if (o.pnl or 0) > 0)
                win_rate = (winners / total_trades * 100) if total_trades > 0 else 0

                old_session.final_balance = account.balance
                old_session.total_pnl = round(total_pnl, 2)
                old_session.total_trades = total_trades
                old_session.win_rate = round(win_rate, 2)
                old_session.status = "archived"
                old_session.ended_at = now

        from sqlalchemy import update

        # Archive open/settled orders (mark status so active queries exclude them)
        self.db.execute(
            update(PaperOrder)
            .where(
                PaperOrder.session_id == old_session_id,
                PaperOrder.status.in_(["open", "settled"])
            )
            .values(status="archived")
        )

        # Archive open positions
        self.db.execute(
            update(PaperPosition)
            .where(
                PaperPosition.session_id == old_session_id,
                PaperPosition.status == "open"
            )
            .values(status="archived")
        )

        # Archive daily returns
        self.db.execute(
            update(PaperDailyReturn)
            .where(
                PaperDailyReturn.session_id == old_session_id,
                PaperDailyReturn.status == "active"
            )
            .values(status="archived")
        )

        # ── Create new session ───────────────────────────────────────────
        new_session = self._create_session()
        account.balance = account.initial_balance
        account.active_session_id = new_session.id

        self.db.commit()
        self.db.refresh(account)
        return account

    # ── Orders ───────────────────────────────────────────────────────────

    def list_orders(self) -> list[PaperOrder]:
        """Fetch orders from the active session, ordered by newest first."""
        session = self.get_active_session()
        return list(self.db.scalars(
            select(PaperOrder)
            .where(
                PaperOrder.session_id == session.id,
                PaperOrder.status != "archived",
            )
            .order_by(PaperOrder.trade_date.desc(), PaperOrder.created_at.desc())
        ).all())

    def create_long_order(
        self,
        data: PaperOrderCreate,
        strategy_name: str | None = None,
    ) -> PaperOrder | None:
        account = self.get_account()
        session = self.get_active_session()

        cost = data.entry_price * data.quantity
        if account.balance < cost:
            return None

        # Deduct balance
        account.balance -= cost

        order = PaperOrder(
            session_id=session.id,
            run_id=data.run_id,
            snapshot_id=data.snapshot_id,
            stock_code=data.stock_code,
            stock_name=data.stock_name,
            strategy_name=strategy_name,
            trade_date=data.trade_date,
            side="buy",
            status="open",
            entry_price=data.entry_price,
            quantity=data.quantity,
        )
        self.db.add(order)

        # ── Upsert position ──────────────────────────────────────────────
        existing_pos = self.db.scalars(
            select(PaperPosition).where(
                PaperPosition.session_id == session.id,
                PaperPosition.stock_code == data.stock_code,
                PaperPosition.status == "open",
            )
        ).first()

        now = datetime.now(UTC)

        if existing_pos:
            total_qty = existing_pos.quantity + data.quantity
            existing_pos.average_price = (
                (existing_pos.average_price * existing_pos.quantity)
                + (data.entry_price * data.quantity)
            ) / total_qty
            existing_pos.quantity = total_qty
            existing_pos.market_value = existing_pos.average_price * total_qty
            existing_pos.updated_at = now
        else:
            pos = PaperPosition(
                session_id=session.id,
                strategy_name=strategy_name,
                stock_code=data.stock_code,
                stock_name=data.stock_name,
                quantity=data.quantity,
                average_price=data.entry_price,
                market_value=data.entry_price * data.quantity,
                pnl=0,
                return_pct=0,
                status="open",
                opened_at=now,
                updated_at=now,
            )
            self.db.add(pos)

        self.db.commit()
        self.db.refresh(order)
        return order

    # ── Settlement ───────────────────────────────────────────────────────

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

        # Return capital to account
        account = self.get_account()
        proceeds = close_price * order.quantity
        account.balance += proceeds

        # Update / close position
        pos = self.db.scalars(
            select(PaperPosition).where(
                PaperPosition.session_id == order.session_id,
                PaperPosition.stock_code == order.stock_code,
                PaperPosition.status == "open",
            )
        ).first()
        if pos:
            pos.quantity -= order.quantity
            if pos.quantity <= 0:
                pos.quantity = 0
                pos.status = "archived"
                pos.market_value = 0
                pos.pnl = 0
                pos.return_pct = 0
            else:
                pos.market_value = pos.average_price * pos.quantity
            pos.updated_at = datetime.now(UTC)

        self.db.commit()
        self.db.refresh(order)
        return order

    def settle_open_orders(self, price_map: dict[str, float]) -> list[PaperOrder]:
        """Settle all open orders in the active session."""
        session = self.get_active_session()
        open_orders = self.db.scalars(
            select(PaperOrder).where(
                PaperOrder.session_id == session.id,
                PaperOrder.status == "open",
            )
        ).all()

        settled = []
        for order in open_orders:
            close_price = price_map.get(order.stock_code)
            if close_price is None:
                continue
            self.settle_order(order, close_price)
            settled.append(order)

        return settled

    # ── Daily Returns ────────────────────────────────────────────────────

    def record_daily_return(self, trade_date: date, strategy_name: str | None = None) -> PaperDailyReturn | None:
        """Aggregate settled orders for a given date into a daily return record."""
        session = self.get_active_session()
        settled_orders = self.db.scalars(
            select(PaperOrder).where(
                PaperOrder.session_id == session.id,
                PaperOrder.trade_date == trade_date,
                PaperOrder.status == "settled",
            )
        ).all()

        if not settled_orders:
            return None

        total_pnl = sum(o.pnl or 0 for o in settled_orders)
        total_orders = len(settled_orders)
        winners = sum(1 for o in settled_orders if (o.pnl or 0) > 0)
        win_rate = (winners / total_orders * 100) if total_orders > 0 else 0

        account = self.get_account()
        return_pct = (total_pnl / account.initial_balance) * 100 if account.initial_balance > 0 else 0

        # strategy_name is left empty as daily return is a session-level aggregate
        strategy_name = None

        order_details = [
            {
                "code": o.stock_code,
                "name": o.stock_name,
                "strategy": o.strategy_name,
                "entry_price": o.entry_price,
                "close_price": o.close_price,
                "quantity": o.quantity,
                "pnl": o.pnl,
                "return_pct": o.return_pct,
            }
            for o in settled_orders
        ]

        # Upsert within session + date
        existing = self.db.scalars(
            select(PaperDailyReturn).where(
                PaperDailyReturn.session_id == session.id,
                PaperDailyReturn.trade_date == trade_date,
            )
        ).first()

        if existing:
            existing.total_orders = total_orders
            existing.win_rate = round(win_rate, 2)
            existing.total_pnl = round(total_pnl, 2)
            existing.return_pct = round(return_pct, 4)
            existing.strategy_name = strategy_name
            existing.details = {"orders": order_details}
            self.db.commit()
            self.db.refresh(existing)
            return existing

        dr = PaperDailyReturn(
            session_id=session.id,
            trade_date=trade_date,
            total_orders=total_orders,
            win_rate=round(win_rate, 2),
            total_pnl=round(total_pnl, 2),
            return_pct=round(return_pct, 4),
            strategy_name=strategy_name,
            status="active",
            details={"orders": order_details},
        )
        self.db.add(dr)
        self.db.commit()
        self.db.refresh(dr)
        return dr

    # ── Positions ────────────────────────────────────────────────────────

    def list_positions(self) -> list[PaperPosition]:
        """Return all open positions in the active session."""
        session = self.get_active_session()
        return list(self.db.scalars(
            select(PaperPosition)
            .where(
                PaperPosition.session_id == session.id,
                PaperPosition.status == "open",
            )
            .order_by(PaperPosition.opened_at.desc())
        ).all())

    # ── Statistics ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Compute aggregate statistics from the active session."""
        account = self.get_account()
        session = self.get_active_session()

        total_settled = self.db.scalar(
            select(func.count(PaperOrder.id)).where(
                PaperOrder.session_id == session.id,
                PaperOrder.status == "settled",
            )
        ) or 0

        total_pnl = self.db.scalar(
            select(func.sum(PaperOrder.pnl)).where(
                PaperOrder.session_id == session.id,
                PaperOrder.status == "settled",
            )
        ) or 0.0

        winners = self.db.scalar(
            select(func.count(PaperOrder.id)).where(
                PaperOrder.session_id == session.id,
                PaperOrder.status == "settled",
                PaperOrder.pnl > 0,
            )
        ) or 0

        win_rate = (winners / total_settled * 100) if total_settled > 0 else 0

        all_active_count = self.db.scalar(
            select(func.count(PaperOrder.id)).where(
                PaperOrder.session_id == session.id,
                PaperOrder.status.in_(["open", "settled"]),
            )
        ) or 0

        cumulative_pnl_pct = (total_pnl / account.initial_balance * 100) if account.initial_balance > 0 else 0

        open_positions = self.list_positions()
        positions_market_value = sum(p.market_value for p in open_positions)
        total_assets = account.balance + positions_market_value

        annualized_return = 0.0
        if total_settled > 0:
            min_date = self.db.scalar(
                select(func.min(PaperOrder.trade_date)).where(
                    PaperOrder.session_id == session.id,
                    PaperOrder.status == "settled"
                )
            )
            max_date = self.db.scalar(
                select(func.max(PaperOrder.trade_date)).where(
                    PaperOrder.session_id == session.id,
                    PaperOrder.status == "settled"
                )
            )
            if min_date and max_date:
                date_range = (max_date - min_date).days
                if date_range > 0:
                    daily_return = total_pnl / account.initial_balance / date_range
                    annualized_return = round(daily_return * 252 * 100, 2)

        daily_returns = list(self.db.scalars(
            select(PaperDailyReturn).where(
                PaperDailyReturn.session_id == session.id,
                PaperDailyReturn.status == "active",
            ).order_by(PaperDailyReturn.trade_date)
        ).all())
        max_drawdown = 0.0
        if daily_returns:
            cumulative = 0.0
            peak = 0.0
            for dr in daily_returns:
                cumulative += dr.total_pnl
                if cumulative > peak:
                    peak = cumulative
                drawdown = peak - cumulative
                if peak > 0 and (drawdown / peak) > max_drawdown:
                    max_drawdown = drawdown / peak
            max_drawdown = round(max_drawdown * 100, 2)

        return {
            "session_id": session.id,
            "session_label": session.label,
            "total_assets": round(total_assets, 2),
            "balance": round(account.balance, 2),
            "initial_balance": account.initial_balance,
            "cumulative_pnl": round(total_pnl, 2),
            "cumulative_pnl_pct": round(cumulative_pnl_pct, 4),
            "annualized_return": annualized_return,
            "max_drawdown": max_drawdown,
            "win_rate": round(win_rate, 2),
            "total_trades": total_settled,
            "open_orders": all_active_count - total_settled,
            "positions_market_value": round(positions_market_value, 2),
        }

    def get_net_value_series(self) -> list[dict]:
        """Return daily net-value points from the active session."""
        session = self.get_active_session()
        daily_returns = list(self.db.scalars(
            select(PaperDailyReturn).where(
                PaperDailyReturn.session_id == session.id,
                PaperDailyReturn.status == "active",
            ).order_by(PaperDailyReturn.trade_date)
        ).all())

        account = self.get_account()
        base = account.initial_balance
        cumulative = 0.0
        series = []
        for dr in daily_returns:
            cumulative += dr.total_pnl
            series.append({
                "date": dr.trade_date.isoformat(),
                "value": round(base + cumulative, 2),
                "pnl": round(dr.total_pnl, 2),
            })
        return series

    # ── History (for LLM reports) ────────────────────────────────────────

    def list_sessions(self, include_active: bool = True) -> list[PaperSession]:
        """Return all sessions for LLM analysis, newest first."""
        query = select(PaperSession).order_by(PaperSession.started_at.desc())
        if not include_active:
            query = query.where(PaperSession.status == "archived")
        return list(self.db.scalars(query).all())

    def get_session_detail(self, session_id: str) -> dict:
        """Return full detail of a session — orders, positions, daily returns.
        
        This provides the rich sample data LLM needs for daily/monthly reports.
        """
        session = self.db.get(PaperSession, session_id)
        if not session:
            return {"error": "session_not_found"}

        orders = list(self.db.scalars(
            select(PaperOrder)
            .where(PaperOrder.session_id == session_id)
            .order_by(PaperOrder.trade_date.desc())
        ).all())

        daily_returns = list(self.db.scalars(
            select(PaperDailyReturn)
            .where(PaperDailyReturn.session_id == session_id)
            .order_by(PaperDailyReturn.trade_date)
        ).all())

        # Group orders by strategy
        strategy_breakdown: dict[str, dict] = {}
        for o in orders:
            sname = o.strategy_name or "unknown"
            if sname not in strategy_breakdown:
                strategy_breakdown[sname] = {"count": 0, "pnl": 0, "winners": 0}
            strategy_breakdown[sname]["count"] += 1
            strategy_breakdown[sname]["pnl"] += o.pnl or 0
            if (o.pnl or 0) > 0:
                strategy_breakdown[sname]["winners"] += 1

        for sname, data in strategy_breakdown.items():
            data["win_rate"] = round(
                (data["winners"] / data["count"] * 100) if data["count"] > 0 else 0, 2
            )
            data["pnl"] = round(data["pnl"], 2)

        # Group orders by date
        date_breakdown: dict[str, dict] = {}
        for o in orders:
            d = o.trade_date.isoformat()
            if d not in date_breakdown:
                date_breakdown[d] = {"count": 0, "pnl": 0, "winners": 0, "stocks": []}
            date_breakdown[d]["count"] += 1
            date_breakdown[d]["pnl"] += o.pnl or 0
            if (o.pnl or 0) > 0:
                date_breakdown[d]["winners"] += 1
            date_breakdown[d]["stocks"].append({
                "code": o.stock_code,
                "name": o.stock_name,
                "strategy": o.strategy_name,
                "entry_price": o.entry_price,
                "close_price": o.close_price,
                "pnl": o.pnl,
                "return_pct": o.return_pct,
                "status": o.status,
            })

        return {
            "session": {
                "id": session.id,
                "label": session.label,
                "status": session.status,
                "initial_balance": session.initial_balance,
                "final_balance": session.final_balance,
                "total_pnl": session.total_pnl,
                "total_trades": session.total_trades,
                "win_rate": session.win_rate,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            },
            "strategy_breakdown": strategy_breakdown,
            "date_breakdown": date_breakdown,
            "daily_returns": [
                {
                    "trade_date": dr.trade_date.isoformat(),
                    "total_orders": dr.total_orders,
                    "win_rate": dr.win_rate,
                    "total_pnl": dr.total_pnl,
                    "return_pct": dr.return_pct,
                    "strategy_name": dr.strategy_name,
                    "details": dr.details,
                }
                for dr in daily_returns
            ],
            "total_orders": len(orders),
        }

    def get_all_history_for_report(self, period_start: date | None = None, period_end: date | None = None) -> dict:
        """Aggregate data across ALL sessions for LLM monthly/weekly reports.
        
        Returns cross-session statistics that let the LLM compare performance
        across different strategy configurations and time periods.
        """
        all_sessions = self.list_sessions()

        # Per-session summaries
        session_summaries = []
        for s in all_sessions:
            session_summaries.append({
                "id": s.id,
                "label": s.label,
                "status": s.status,
                "initial_balance": s.initial_balance,
                "final_balance": s.final_balance,
                "total_pnl": s.total_pnl,
                "total_trades": s.total_trades,
                "win_rate": s.win_rate,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            })

        # Cross-session strategy performance using SQL aggregation
        from sqlalchemy import case
        query = select(
            PaperOrder.strategy_name,
            func.count(PaperOrder.id).label('count'),
            func.sum(PaperOrder.pnl).label('pnl'),
            func.sum(case((PaperOrder.pnl > 0, 1), else_=0)).label('winners')
        ).where(PaperOrder.status == "settled")
        
        if period_start:
            query = query.where(PaperOrder.trade_date >= period_start)
        if period_end:
            query = query.where(PaperOrder.trade_date <= period_end)
            
        query = query.group_by(PaperOrder.strategy_name)
        rows = self.db.execute(query).all()

        strategy_perf: dict[str, dict] = {}
        for row in rows:
            sname = row.strategy_name or "unknown"
            count = row.count or 0
            winners = row.winners or 0
            pnl = row.pnl or 0.0
            strategy_perf[sname] = {
                "count": count,
                "pnl": round(pnl, 2),
                "winners": winners,
                "win_rate": round((winners / count * 100) if count > 0 else 0, 2)
            }

        return {
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "total_sessions": len(all_sessions),
            "session_summaries": session_summaries,
            "cross_session_strategy_performance": strategy_perf,
            "total_orders_in_period": len(all_orders),
        }
