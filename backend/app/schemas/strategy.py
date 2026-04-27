from pydantic import BaseModel, Field


class StrategySignal(BaseModel):
    stock_code: str
    stock_name: str | None = None
    strategy_name: str
    matched: bool
    reason: str
    score: float = 0
    metrics: dict = Field(default_factory=dict)
