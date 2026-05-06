from datetime import date, datetime

from fastapi import APIRouter, Query

from app.services.data.service import MarketDataService

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/bars/{code}")
def get_market_bars(
    code: str,
    period: str = Query("5", description="Bar period: 5, 15, 30, 60 (minutes)"),
    start: str = Query("", description="Start date YYYYMMDD"),
    end: str = Query("", description="End date YYYYMMDD"),
):
    svc = MarketDataService()
    today = date.today()
    start_date = _parse_date(start) or today
    end_date = _parse_date(end) or today
    bars = svc.get_minute_bars(code, start_date, end_date, period)
    return {
        "code": code,
        "period": period,
        "bars": [b.model_dump() for b in bars],
    }


@router.get("/quote/{code}")
def get_market_quote(code: str):
    svc = MarketDataService()
    quote = svc.get_quote(code)
    return quote.model_dump()


def _parse_date(s: str) -> date | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y%m%d").date()
    except ValueError:
        return None
