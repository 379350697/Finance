from datetime import date
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm.report_service import build_fallback_daily_report

router = APIRouter(prefix="/reports", tags=["reports"])

_reports: dict[str, dict] = {}


class GenerateReportRequest(BaseModel):
    period_type: str = "daily"
    period_start: date
    period_end: date
    candidates_count: int = 0
    orders_count: int = 0
    total_return_pct: float = 0


@router.post("/generate")
def generate_report(request: GenerateReportRequest) -> dict:
    report_id = str(uuid4())
    content = build_fallback_daily_report(
        trade_date=request.period_end.isoformat(),
        candidates_count=request.candidates_count,
        orders_count=request.orders_count,
        total_return_pct=request.total_return_pct,
    )
    report = {
        "id": report_id,
        "period_type": request.period_type,
        "period_start": request.period_start.isoformat(),
        "period_end": request.period_end.isoformat(),
        "title": f"{request.period_end.isoformat()} 研报",
        "content": content,
        "provider": "openai_codex",
        "status": "generated",
    }
    _reports[report_id] = report
    return report


@router.get("")
def list_reports() -> list[dict]:
    return list(_reports.values())


@router.get("/{report_id}")
def get_report(report_id: str) -> dict:
    return _reports.get(report_id, {"id": report_id, "status": "not_found"})
