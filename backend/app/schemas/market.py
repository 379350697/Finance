from datetime import date, datetime

from pydantic import BaseModel


class StockQuote(BaseModel):
    code: str
    name: str
    price: float
    change_pct: float | None = None
    volume: float | None = None
    turnover: float | None = None


class StockInfo(BaseModel):
    code: str
    name: str
    market: str | None = None
    exchange: str | None = None
    industry: str | None = None


class DailyBar(BaseModel):
    code: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None


class MinuteBar(BaseModel):
    code: str
    trade_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    turnover: float | None = None
