from datetime import date

from pydantic import BaseModel, Field


class StockSnapshotCreate(BaseModel):
    stock_code: str
    stock_name: str
    trade_date: date
    run_id: str | None = None
    candidate_id: str | None = None
    quote_data: dict = Field(default_factory=dict)
    indicator_data: dict = Field(default_factory=dict)
    strategy_data: dict = Field(default_factory=dict)
    news_data: dict | None = None
    raw_data: dict = Field(default_factory=dict)
