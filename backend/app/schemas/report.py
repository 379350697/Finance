from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ReportPeriod = Literal["daily", "weekly", "monthly"]


class ReportGenerateRequest(BaseModel):
    period_type: ReportPeriod = "daily"
    period_start: date
    period_end: date


class ReportCreate(BaseModel):
    period_type: ReportPeriod
    period_start: date
    period_end: date
    title: str
    content: str
    input_summary: dict = Field(default_factory=dict)
    suggestions: dict = Field(default_factory=dict)
    provider: str = "openai_codex"
    model: str | None = None
    status: str = "generated"
    error_message: str | None = None
