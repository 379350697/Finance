from fastapi import APIRouter

from app.schemas.backtest import BacktestRequest, BacktestResult
from app.services.backtest import BacktestService

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run")
def run_backtest(request: BacktestRequest) -> BacktestResult:
    return BacktestService().run(request)
